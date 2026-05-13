"""
build_font_db.py — 字体特征库生成脚本（一次性运行）

对每个注册字体渲染标准汉字，测量视觉参数，输出 font_features.json。
"""

import json
import sys
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from font_config import FONT_REGISTRY

# 标准测试字符
# 笔画多样：横竖撇捺折钩点，覆盖不同结构
TEST_CHARS_CJK = "永东国酬鹰中大小"
TEST_CHARS_LATIN = "ABCDEFGHabcdefgh0123456789"

RENDER_SIZE = 120  # 渲染字号（像素）
CANVAS_SIZE = 200  # 画布大小


def render_char(font_path: str, char: str, size: int = RENDER_SIZE):
    """渲染单个字符为二值化 numpy 数组"""
    try:
        font = ImageFont.truetype(font_path, size)
    except Exception as e:
        return None

    img = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 255)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), char, font=font)
    # 居中绘制
    x = (CANVAS_SIZE - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (CANVAS_SIZE - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), char, font=font, fill=0)

    arr = np.array(img)
    # 二值化：< 128 为笔画
    binary = (arr < 128).astype(np.uint8)
    return binary


def measure_stroke_weight(binary: np.ndarray) -> float:
    """
    测量笔画粗细：笔画像素占比。
    值越大 = 字越粗。
    """
    return float(np.sum(binary)) / binary.size


def measure_width_ratio(font_path: str, char: str, size: int = RENDER_SIZE):
    """
    测量字宽高比：渲染后 bounding box 的 width / height。
    """
    try:
        font = ImageFont.truetype(font_path, size)
    except Exception:
        return None

    img = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 255)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), char, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    if h <= 0:
        return None
    return w / h


def measure_variance(binaries):
    """
    测量笔画粗细变化率（跨多个字符的 weight 标准差）。
    黑体方差小，宋体方差中等，毛笔方差大。
    """
    weights = [measure_stroke_weight(b) for b in binaries if b is not None]
    if len(weights) < 2:
        return 0.0
    return float(np.std(weights))


def measure_stroke_ratio(binary: np.ndarray) -> float:
    """
    测量横竖笔画宽度比 (horizontal_stroke / vertical_stroke)。
    
    用 run-length 分析：
    - 沿列方向采样，每列中连续笔画段的中位长度 ≈ 横笔画粗细
    - 沿行方向采样，每行中连续笔画段的中位长度 ≈ 竖笔画粗细
    
    宋体：横细竖粗，比值 < 0.6
    黑体：横竖均匀，比值 0.7~1.0
    """
    h, w = binary.shape
    if h < 10 or w < 10:
        return 1.0

    def median_run_length(axis_binary, axis):
        """沿指定轴采样 run-length"""
        runs = []
        size = axis_binary.shape[axis]
        step = max(1, size // 20)
        indices = range(0, size, step)

        for idx in indices:
            if axis == 0:
                line = axis_binary[idx, :]
            else:
                line = axis_binary[:, idx]

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

    # 横笔画粗细：沿列方向采样
    h_stroke = median_run_length(binary, axis=1)
    # 竖笔画粗细：沿行方向采样
    v_stroke = median_run_length(binary, axis=0)

    if v_stroke < 1:
        return 1.0

    return h_stroke / v_stroke


def build_features_for_font(font_id, font_info):
    """为单个字体计算特征"""
    font_path = font_info["path"]
    category = font_info["category"]

    if not os.path.exists(font_path):
        print(f"  ✗ {font_id}: 文件不存在 {font_path}")
        return None

    # 选择测试字符
    if category == "digit":
        test_chars = TEST_CHARS_LATIN
    else:
        test_chars = TEST_CHARS_CJK

    # 渲染所有测试字符
    binaries = []
    width_ratios = []
    for char in test_chars:
        binary = render_char(font_path, char)
        if binary is not None:
            binaries.append(binary)
        wr = measure_width_ratio(font_path, char)
        if wr is not None:
            width_ratios.append(wr)

    if not binaries:
        print(f"  ✗ {font_id}: 无法渲染任何字符")
        return None

    # 计算三个核心参数 + stroke_ratio
    weights = [measure_stroke_weight(b) for b in binaries]
    avg_weight = float(np.mean(weights))
    avg_width_ratio = float(np.mean(width_ratios)) if width_ratios else 1.0
    variance = measure_variance(binaries)

    # stroke_ratio: 横竖笔画宽度比
    stroke_ratios = [measure_stroke_ratio(b) for b in binaries]
    avg_stroke_ratio = float(np.mean(stroke_ratios)) if stroke_ratios else 1.0

    return {
        "category": category,
        "weight": round(avg_weight, 5),
        "width_ratio": round(avg_width_ratio, 4),
        "variance": round(variance, 6),
        "stroke_ratio": round(avg_stroke_ratio, 4),
        "pptx_name": font_info["pptx_name"],
        "path": font_path,
    }


def main():
    print("=" * 50)
    print("  字体特征库生成")
    print("=" * 50)

    features = {}
    success = 0
    fail = 0

    for font_id, font_info in FONT_REGISTRY.items():
        result = build_features_for_font(font_id, font_info)
        if result:
            features[font_id] = result
            print(f"  ✓ {font_id}: weight={result['weight']:.4f} "
                  f"width_ratio={result['width_ratio']:.3f} "
                  f"variance={result['variance']:.5f} "
                  f"stroke_ratio={result['stroke_ratio']:.3f}")
            success += 1
        else:
            fail += 1

    # 输出 JSON
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font_features.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"  完成: {success} 成功, {fail} 失败")
    print(f"  输出: {output_path}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
