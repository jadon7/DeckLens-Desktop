"""
font_matcher.py — 字体匹配核心逻辑

输入：一张文字区域的图片（OCR 截取的 bbox 区域）
输出：最匹配的字体名（pptx_name）

可作为独立脚本调用：
  python3 font_matcher.py <image_path> [--json]

也可作为模块导入：
  from font_matcher import match_font
"""

import json
import os
import re
import sys
import numpy as np
from PIL import Image

# 特征库路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURES_PATH = os.path.join(SCRIPT_DIR, "font_features.json")

# 加载特征库（模块级缓存）
_features_cache = None


def load_features():
    global _features_cache
    if _features_cache is None:
        with open(FEATURES_PATH, "r", encoding="utf-8") as f:
            _features_cache = json.load(f)
    return _features_cache


def classify_text(text):
    """
    判断文本大类：
    - 'digit': 纯数字/英文
    - 'cjk': 含中文
    """
    # 纯英文数字符号
    if re.match(r'^[0-9A-Za-z\s\-_\.,:;!?@#$%&*()+=\[\]{}<>/\\|~`\'"]+$', text.strip()):
        return "digit"
    return "cjk"


def _measure_stroke_ratio(binary):
    """
    测量横竖笔画宽度比 (horizontal_stroke / vertical_stroke)。
    
    原理：
    - 水平投影（按行求和）的峰值宽度 ≈ 横笔画粗细
    - 垂直投影（按列求和）的峰值宽度 ≈ 竖笔画粗细
    - 宋体：横细竖粗，比值 < 0.6
    - 黑体：横竖均匀，比值 0.7~1.0
    
    返回: float (ratio)，失败返回 1.0（默认黑体）
    """
    h, w = binary.shape
    if h < 10 or w < 10:
        return 1.0

    # 水平投影：每行笔画像素数
    h_proj = np.sum(binary, axis=1).astype(float)
    # 垂直投影：每列笔画像素数
    v_proj = np.sum(binary, axis=0).astype(float)

    # 取投影中有笔画的部分（非零行/列）
    h_nonzero = h_proj[h_proj > 0]
    v_nonzero = v_proj[v_proj > 0]

    if len(h_nonzero) < 5 or len(v_nonzero) < 5:
        return 1.0

    # 用中位数代表典型笔画宽度（比均值更鲁棒，不受长横/长竖影响）
    # 水平投影的中位数 = 典型行中横向笔画覆盖的像素数 → 反映竖笔画的粗细
    # 垂直投影的中位数 = 典型列中纵向笔画覆盖的像素数 → 反映横笔画的粗细
    #
    # 但更直接的方法：用 run-length 分析
    # 对每行，找连续 1 的段（笔画段），取中位长度 = 横笔画宽度的代理
    # 对每列，找连续 1 的段，取中位长度 = 竖笔画宽度的代理

    def median_run_length(projection, axis_binary, axis):
        """沿指定轴采样 run-length"""
        runs = []
        # 采样部分行/列以提高速度
        size = axis_binary.shape[axis]
        step = max(1, size // 20)
        indices = range(0, size, step)

        for idx in indices:
            if axis == 0:
                line = axis_binary[idx, :]
            else:
                line = axis_binary[:, idx]

            # 找连续 1 的 run
            in_run = False
            run_len = 0
            for px in line:
                if px:
                    in_run = True
                    run_len += 1
                else:
                    if in_run and run_len >= 2:
                        runs.append(run_len)
                    in_run = False
                    run_len = 0
            if in_run and run_len >= 2:
                runs.append(run_len)

        if not runs:
            return 0.0
        return float(np.median(runs))

    # 横笔画粗细：沿垂直方向（列）采样，每列中连续 1 的段长度 = 横笔画的高度（粗细）
    h_stroke = median_run_length(v_proj, binary, axis=1)
    # 竖笔画粗细：沿水平方向（行）采样，每行中连续 1 的段长度 = 竖笔画的宽度（粗细）
    v_stroke = median_run_length(h_proj, binary, axis=0)

    if v_stroke < 1:
        return 1.0

    return h_stroke / v_stroke


def measure_image_features(image_region):
    """
    从图片区域测量视觉特征。
    
    image_region: numpy array (H, W) 灰度图 或 (H, W, 3) RGB
    
    返回: {weight, width_ratio, variance, stroke_ratio}
    """
    if image_region is None or image_region.size == 0:
        return None

    # 转灰度
    if len(image_region.shape) == 3:
        gray = np.mean(image_region, axis=2).astype(np.uint8)
    else:
        gray = image_region

    h, w = gray.shape

    # 自适应二值化：判断是亮底暗字还是暗底亮字
    mean_val = np.mean(gray)
    if mean_val > 127:
        # 亮底暗字：暗像素是笔画
        threshold = mean_val * 0.6
        binary = (gray < threshold).astype(np.uint8)
    else:
        # 暗底亮字：亮像素是笔画
        threshold = mean_val + (255 - mean_val) * 0.4
        binary = (gray > threshold).astype(np.uint8)

    # weight: 笔画像素占比
    weight = float(np.sum(binary)) / binary.size

    # 如果笔画太少，可能是空白区域
    if weight < 0.01:
        return None

    # width_ratio: 找到笔画的 bounding box
    rows = np.any(binary, axis=1)
    cols = np.any(binary, axis=0)
    if not np.any(rows) or not np.any(cols):
        return None

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    bbox_h = rmax - rmin + 1
    bbox_w = cmax - cmin + 1
    width_ratio = bbox_w / max(bbox_h, 1)

    # variance: 将区域分成若干竖条，测量每条的 weight 差异
    n_strips = min(8, w // 5)
    if n_strips < 2:
        variance = 0.0
    else:
        strip_w = w // n_strips
        strip_weights = []
        for i in range(n_strips):
            strip = binary[:, i * strip_w:(i + 1) * strip_w]
            sw = float(np.sum(strip)) / max(strip.size, 1)
            strip_weights.append(sw)
        variance = float(np.std(strip_weights))

    # stroke_ratio: 横竖笔画宽度比（宋体判断核心特征）
    stroke_ratio = _measure_stroke_ratio(binary)

    return {
        "weight": weight,
        "width_ratio": width_ratio,
        "variance": variance,
        "stroke_ratio": stroke_ratio,
    }


def classify_category(features, text):
    """
    根据视觉特征和文本内容判断字体大类。
    返回: 'heiti', 'songti', 'maobi', 'digit'
    
    策略：结合 stroke_ratio（横竖笔画宽度比）+ 保守阈值
    - stroke_ratio < 0.75 → 宋体（横细竖粗明显）
    - stroke_ratio >= 0.75 → 黑体（默认）
    - 纯英文/数字 → digit
    
    stroke_ratio 是结构性特征，比 variance 更鲁棒，不易被背景渐变/阴影干扰。
    阈值设得保守（0.75），宁可漏判宋体也不误判黑体为宋体。
    """
    text_type = classify_text(text)
    if text_type == "digit":
        return "digit"

    stroke_ratio = features.get("stroke_ratio", 1.0)

    # 保守策略：只有 stroke_ratio 非常明确时才判定宋体
    # 字体库实测数据：
    #   黑体 stroke_ratio: 0.91 ~ 1.27（横竖均匀）
    #   宋体 stroke_ratio: 0.51 ~ 0.88（横细竖粗）
    # 分界线约 0.88~0.91，但图片测量有噪声，取保守阈值 0.75
    # 这样能覆盖明显的宋体（dream-serif, flower-fangsong），不会误判黑体
    if stroke_ratio < 0.75:
        return "songti"

    return "heiti"


def match_font(image_region, text=""):
    """
    核心匹配函数。
    
    参数:
        image_region: numpy array，文字区域图片（灰度或 RGB）
        text: OCR 识别出的文字内容（用于辅助判断大类）
    
    返回:
        {
            "font_id": "misans-regular",
            "pptx_name": "MiSans",
            "category": "heiti",
            "confidence": 0.85,
        }
    """
    features_db = load_features()

    # 测量输入图片的视觉特征
    measured = measure_image_features(image_region)
    if measured is None:
        # 无法测量，返回默认字体
        return {
            "font_id": "misans-regular",
            "pptx_name": "MiSans",
            "category": "heiti",
            "confidence": 0.0,
        }

    # 判断大类
    category = classify_category(measured, text)

    # 在对应大类中查找最近的字体
    candidates = {
        fid: feat for fid, feat in features_db.items()
        if feat["category"] == category
    }

    # 如果该类别没有字体，扩大到全部
    if not candidates:
        candidates = features_db

    # 计算距离（只用 weight）
    # width_ratio 从图片测量的是整行文字的宽高比，和单字渲染的特征库不可比
    # weight（笔画像素占比）是唯一在两种场景下都稳定的参数
    #
    # 但图片测量的 weight 因背景干扰通常偏高（背景渐变/阴影被计入笔画）
    # 需要做缩放：将测量值映射到字体库的 weight 范围
    measured_weight = measured["weight"]

    # 获取当前类别字体的 weight 范围
    cat_weights = [feat["weight"] for feat in candidates.values()]
    db_min = min(cat_weights)
    db_max = max(cat_weights)

    # 图片测量值通常在 0.10 ~ 0.50 范围（受背景干扰）
    # 字体库值在 0.05 ~ 0.17 范围（纯渲染）
    # 做线性映射：将测量值压缩到字体库范围
    # 经验值：图片中 weight < 0.15 对应细体，0.15-0.25 对应中等，> 0.25 对应粗体
    img_min = 0.10  # 图片中最细文字的典型 weight
    img_max = 0.45  # 图片中最粗文字的典型 weight

    if img_max > img_min:
        normalized_weight = db_min + (measured_weight - img_min) / (img_max - img_min) * (db_max - db_min)
        normalized_weight = max(db_min, min(db_max, normalized_weight))
    else:
        normalized_weight = (db_min + db_max) / 2

    best_id = None
    best_dist = float("inf")
    for fid, feat in candidates.items():
        dw = abs(normalized_weight - feat["weight"])
        if dw < best_dist:
            best_dist = dw
            best_id = fid

    if best_id is None:
        best_id = "misans-regular"

    matched = features_db[best_id]

    # 置信度：距离越小越高，归一化到 0-1
    confidence = max(0.0, 1.0 - best_dist * 5)

    return {
        "font_id": best_id,
        "pptx_name": matched["pptx_name"],
        "category": matched["category"],
        "confidence": round(confidence, 3),
    }


def match_font_from_file(image_path, text=""):
    """从图片文件路径匹配字体"""
    img = Image.open(image_path)
    arr = np.array(img)
    return match_font(arr, text)


# ─── CLI 接口 ───

def main():
    """
    CLI 用法:
      python3 font_matcher.py <image_path> [text] [--json]
      
    输出 JSON:
      {"font_id": "...", "pptx_name": "...", "category": "...", "confidence": 0.85}
    """
    if len(sys.argv) < 2:
        print("用法: python3 font_matcher.py <image_path> [text] [--json]")
        sys.exit(1)

    image_path = sys.argv[1]
    text = ""
    output_json = False

    for arg in sys.argv[2:]:
        if arg == "--json":
            output_json = True
        else:
            text = arg

    result = match_font_from_file(image_path, text)

    if output_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"字体: {result['pptx_name']}")
        print(f"分类: {result['category']}")
        print(f"置信度: {result['confidence']}")


if __name__ == "__main__":
    main()
