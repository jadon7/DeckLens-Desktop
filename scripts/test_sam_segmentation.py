#!/usr/bin/env python3
"""
SAM 元素分割测试脚本
用法: python3 scripts/test_sam_segmentation.py <图片路径> [输出目录]

流程:
1. OCR 检测文字
2. LaMa 擦除文字 → 干净背景图
3. SAM 分割干净背景图
4. 后处理过滤
5. 生成带编号的可视化图 + 统计信息

输出:
- <输出目录>/test_bg_clean.png        — 擦除文字后的干净背景
- <输出目录>/sam_viz.png              — 带编号的分割可视化图
- 终端打印统计信息
"""

import sys
import os
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import colorsys
from PIL import Image, ImageDraw, ImageFont
from engine import detect_text_paddle, remove_text_from_image, get_sam_mask_generator


# ─── 后处理参数（调参时修改这里） ───
MIN_AREA_RATIO = 0.001          # 最小面积占比
MAX_AREA_RATIO = 0.80           # 最大面积占比
BG_COLOR_THRESHOLD = 30.0       # 背景色差异阈值
OVERLAP_IOU_THRESHOLD = 0.7     # 重叠合并阈值


def run_test(img_path: str, output_dir: str = "outputs"):
    """执行完整测试流程"""
    os.makedirs(output_dir, exist_ok=True)

    img = Image.open(img_path)
    img_w, img_h = img.size
    total_area = img_w * img_h
    print(f"图片: {img_path}")
    print(f"尺寸: {img_w}x{img_h}")
    print(f"{'='*60}")

    # Step 1: OCR 检测
    print("\n[Step 1] OCR 检测文字...")
    t0 = time.time()
    blocks = detect_text_paddle(img_path)
    print(f"  检测到 {len(blocks)} 个文字区域 ({time.time()-t0:.1f}s)")

    # Step 2: LaMa 擦除
    print("\n[Step 2] LaMa 擦除文字...")
    t0 = time.time()
    if blocks:
        background = remove_text_from_image(img_path, blocks, device="mps")
    else:
        background = img.convert("RGB")
    bg_clean_path = os.path.join(output_dir, "test_bg_clean.png")
    background.save(bg_clean_path)
    print(f"  擦除完成 ({time.time()-t0:.1f}s)")
    print(f"  干净背景图: {bg_clean_path}")

    # Step 3: SAM 分割
    print("\n[Step 3] SAM 分割...")
    bg_rgb = background.convert("RGB")
    bg_np = np.array(bg_rgb)

    t0 = time.time()
    mask_generator = get_sam_mask_generator("mps")
    masks = mask_generator.generate(bg_np)
    sam_time = time.time() - t0
    print(f"  SAM 推理完成 ({sam_time:.1f}s)")
    print(f"  原始 mask 数量: {len(masks)}")

    # Step 4: 后处理
    print(f"\n[Step 4] 后处理 (参数: min_area={MIN_AREA_RATIO}, max_area={MAX_AREA_RATIO}, bg_thresh={BG_COLOR_THRESHOLD}, iou={OVERLAP_IOU_THRESHOLD})")

    # 4.1 面积过滤
    filtered = [m for m in masks if MIN_AREA_RATIO <= m["area"] / total_area <= MAX_AREA_RATIO]
    print(f"  面积过滤后: {len(filtered)}")

    # 4.2 背景色过滤
    corner_size = max(20, min(img_w, img_h) // 10)
    corners = np.concatenate([
        bg_np[:corner_size, :corner_size].reshape(-1, 3),
        bg_np[:corner_size, -corner_size:].reshape(-1, 3),
        bg_np[-corner_size:, :corner_size].reshape(-1, 3),
        bg_np[-corner_size:, -corner_size:].reshape(-1, 3),
    ], axis=0)
    bg_color = np.median(corners, axis=0)
    print(f"  检测到背景色: RGB({bg_color[0]:.0f}, {bg_color[1]:.0f}, {bg_color[2]:.0f})")

    color_filtered = []
    for m in filtered:
        seg = m["segmentation"]
        mask_mean_color = np.mean(bg_np[seg], axis=0)
        color_diff = np.sqrt(np.sum((mask_mean_color - bg_color) ** 2))
        if color_diff >= BG_COLOR_THRESHOLD:
            color_filtered.append(m)
    print(f"  背景色过滤后: {len(color_filtered)}")

    # 4.3 重叠合并
    color_filtered.sort(key=lambda x: x["area"], reverse=True)
    keep = []
    for m in color_filtered:
        should_keep = True
        seg_m = m["segmentation"]
        for kept in keep:
            seg_k = kept["segmentation"]
            intersection = np.logical_and(seg_m, seg_k).sum()
            union = np.logical_or(seg_m, seg_k).sum()
            if union > 0 and intersection / union > OVERLAP_IOU_THRESHOLD:
                should_keep = False
                break
        if should_keep:
            keep.append(m)
    print(f"  去重后（最终）: {len(keep)}")

    # Step 5: 生成可视化图
    print(f"\n[Step 5] 生成可视化图...")
    vis = bg_rgb.copy().convert("RGBA")
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))

    for idx, m in enumerate(keep):
        hue = idx / max(len(keep), 1)
        r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
        color = (int(r * 255), int(g * 255), int(b * 255), 100)
        seg = m["segmentation"]
        mask_img = Image.fromarray((seg * 255).astype(np.uint8), mode="L")
        colored = Image.new("RGBA", (img_w, img_h), color)
        overlay = Image.composite(colored, overlay, mask_img)

    vis = Image.alpha_composite(vis, overlay).convert("RGB")
    draw = ImageDraw.Draw(vis)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except Exception:
        font = ImageFont.load_default()

    for idx, m in enumerate(keep):
        bbox = m["bbox"]  # [x, y, w, h]
        cx = bbox[0] + bbox[2] // 2
        cy = bbox[1] + bbox[3] // 2
        text = str(idx)
        tb = draw.textbbox((cx, cy), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        draw.rectangle([cx - tw // 2 - 3, cy - th // 2 - 2, cx + tw // 2 + 3, cy + th // 2 + 2], fill=(255, 255, 255))
        draw.text((cx - tw // 2, cy - th // 2), text, fill=(0, 0, 0), font=font)

    viz_path = os.path.join(output_dir, "sam_viz.png")
    vis.save(viz_path, quality=95)
    print(f"  可视化图: {viz_path}")

    # 统计输出
    print(f"\n{'='*60}")
    print(f"结果汇总: {len(keep)} 个元素")
    print(f"{'='*60}")
    print(f"{'编号':>4}  {'面积%':>6}  {'bbox (x,y,wxh)'}")
    print(f"{'-'*4}  {'-'*6}  {'-'*30}")
    for idx, m in enumerate(keep):
        area_pct = m["area"] / total_area * 100
        bbox = m["bbox"]
        print(f"  {idx:2d}    {area_pct:5.1f}%  ({bbox[0]},{bbox[1]},{bbox[2]}x{bbox[3]})")

    print(f"\n输出文件:")
    print(f"  干净背景: {bg_clean_path}")
    print(f"  可视化图: {viz_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_sam_segmentation.py <图片路径> [输出目录]")
        print("示例: python3 scripts/test_sam_segmentation.py uploads/97c780ea/000_*.png outputs/")
        sys.exit(1)

    img_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "outputs"
    run_test(img_path, output_dir)
