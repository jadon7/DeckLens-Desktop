#!/usr/bin/env python3
"""
Local text-fill experiment for DeckLens.

This is intentionally outside the product path. It can remove detected text by:
1. building a per-pixel text mask inside OCR boxes and filling connected components, or
2. treating OCR boxes as rectangles, splitting each box into tiles, fitting a local
   background patch for each tile, and blending the whole box back with soft edges.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import TextBlock, detect_text_paddle, remove_text_from_image  # noqa: E402


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def load_inputs(input_dir: Path, limit: int | None = None) -> list[Path]:
    inputs = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    return inputs[:limit] if limit else inputs


def block_to_dict(block: TextBlock) -> dict[str, Any]:
    data = asdict(block)
    data["color"] = list(block.color)
    return data


def dict_to_block(data: dict[str, Any]) -> TextBlock:
    data = dict(data)
    data["color"] = tuple(data.get("color", (0, 0, 0)))
    return TextBlock(**data)


def get_or_detect_blocks(image_path: Path, cache_dir: Path, force_ocr: bool = False) -> list[TextBlock]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{image_path.stem}.json"
    if cache_path.exists() and not force_ocr:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return [dict_to_block(item) for item in payload["blocks"]]

    blocks = detect_text_paddle(str(image_path), expand_px=3)
    cache_path.write_text(
        json.dumps({"image": str(image_path), "blocks": [block_to_dict(block) for block in blocks]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return blocks


def block_border_pixels(region: np.ndarray) -> np.ndarray:
    h, w = region.shape[:2]
    border = max(2, min(h, w) // 8)
    top = region[:border, :, :].reshape(-1, 3)
    bottom = region[-border:, :, :].reshape(-1, 3)
    left = region[:, :border, :].reshape(-1, 3)
    right = region[:, -border:, :].reshape(-1, 3)
    return np.concatenate([top, bottom, left, right], axis=0)


def build_text_pixel_mask(
    image_rgb: np.ndarray,
    blocks: list[TextBlock],
    min_diff: float,
    mask_dilate: int,
) -> np.ndarray:
    h, w = image_rgb.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    for block in blocks:
        x0 = max(0, block.x)
        y0 = max(0, block.y)
        x1 = min(w, block.x + block.w)
        y1 = min(h, block.y + block.h)
        if x1 <= x0 or y1 <= y0:
            continue

        region = image_rgb[y0:y1, x0:x1]
        border = block_border_pixels(region)
        bg = np.median(border.astype(np.float32), axis=0)
        diff = np.sqrt(np.sum((region.astype(np.float32) - bg) ** 2, axis=2)).astype(np.float32)
        diff_u8 = np.clip(diff, 0, 255).astype(np.uint8)
        otsu_threshold, _ = cv2.threshold(diff_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        threshold = max(float(otsu_threshold), min_diff)
        local = (diff >= threshold).astype(np.uint8)

        # Keep text-like pixels, not the entire OCR rectangle. If detection is
        # too sparse, fall back to a conservative inner rectangle to avoid a no-op.
        if int(local.sum()) < max(8, region.shape[0] * region.shape[1] * 0.003):
            inner_pad = max(1, min(region.shape[:2]) // 10)
            local = np.zeros(region.shape[:2], dtype=np.uint8)
            local[inner_pad : max(inner_pad + 1, region.shape[0] - inner_pad), inner_pad : max(inner_pad + 1, region.shape[1] - inner_pad)] = 1

        mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], local * 255)

    if mask_dilate > 0 and np.any(mask):
        k = mask_dilate * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def component_bbox(component: np.ndarray, pad: int, width: int, height: int) -> tuple[int, int, int, int]:
    ys, xs = np.where(component)
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(width, int(xs.max()) + 1 + pad)
    y1 = min(height, int(ys.max()) + 1 + pad)
    return x0, y0, x1, y1


def feather_alpha(component: np.ndarray, cover_dilate: int, feather_blur: int) -> np.ndarray:
    core = component.astype(np.uint8) * 255
    if cover_dilate > 0:
        k = cover_dilate * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        cover = cv2.dilate(core, kernel, iterations=1)
    else:
        cover = core

    if feather_blur <= 0:
        alpha = cover.astype(np.float32) / 255.0
    else:
        k = feather_blur * 2 + 1
        if k % 2 == 0:
            k += 1
        alpha = cv2.GaussianBlur(cover.astype(np.float32) / 255.0, (k, k), 0)
        if alpha.max() > 0:
            alpha = alpha / alpha.max()
        alpha = np.maximum(alpha, core.astype(np.float32) / 255.0)
    return np.clip(alpha, 0.0, 1.0)


def local_mean_fill(
    image_rgb: np.ndarray,
    text_mask: np.ndarray,
    sample_radius: int,
    cover_dilate: int,
    feather_blur: int,
    min_component_area: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    h, w = image_rgb.shape[:2]
    work = image_rgb.astype(np.float32).copy()
    binary = (text_mask > 0).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    all_text = binary.astype(bool)
    components: list[dict[str, Any]] = []

    for label_id in range(1, num_labels):
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_component_area:
            continue

        component = labels == label_id
        x0, y0, x1, y1 = component_bbox(component, sample_radius + cover_dilate + feather_blur + 2, w, h)
        local_component = component[y0:y1, x0:x1]
        local_all_text = all_text[y0:y1, x0:x1]
        local_image = image_rgb[y0:y1, x0:x1].astype(np.float32)

        k = sample_radius * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        ring_base = cv2.dilate(local_component.astype(np.uint8), kernel, iterations=1).astype(bool)
        sample_region = ring_base & ~local_all_text

        # If the immediate ring is too small, expand once more.
        if int(sample_region.sum()) < 12:
            k2 = max(k + 8, 17)
            kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k2, k2))
            ring_base = cv2.dilate(local_component.astype(np.uint8), kernel2, iterations=1).astype(bool)
            sample_region = ring_base & ~local_all_text

        if int(sample_region.sum()) == 0:
            fill_color = np.median(image_rgb.reshape(-1, 3).astype(np.float32), axis=0)
        else:
            fill_color = np.mean(local_image[sample_region], axis=0)

        alpha = feather_alpha(local_component, cover_dilate=cover_dilate, feather_blur=feather_blur)[..., None]
        patch = np.ones_like(local_image) * fill_color.reshape(1, 1, 3)
        work[y0:y1, x0:x1] = patch * alpha + work[y0:y1, x0:x1] * (1.0 - alpha)

        components.append(
            {
                "area": area,
                "bbox": [int(stats[label_id, cv2.CC_STAT_LEFT]), int(stats[label_id, cv2.CC_STAT_TOP]), int(stats[label_id, cv2.CC_STAT_WIDTH]), int(stats[label_id, cv2.CC_STAT_HEIGHT])],
                "sample_pixels": int(sample_region.sum()),
                "fill_rgb": [round(float(v), 2) for v in fill_color],
            }
        )

    return np.clip(work, 0, 255).astype(np.uint8), components


def numeric_right_pad(block: TextBlock, box_pad: int, symbol_right_pad: int) -> int:
    text = getattr(block, "text", "") or ""
    if any(ch.isdigit() for ch in text):
        return max(box_pad, symbol_right_pad)
    return box_pad


def block_box_mask(image_shape: tuple[int, int], blocks: list[TextBlock], pad: int, symbol_right_pad: int) -> np.ndarray:
    h, w = image_shape
    mask = np.zeros((h, w), dtype=np.uint8)
    for block in blocks:
        right_pad = numeric_right_pad(block, pad, symbol_right_pad)
        x0 = max(0, block.x - pad)
        y0 = max(0, block.y - pad)
        x1 = min(w, block.x + block.w + right_pad)
        y1 = min(h, block.y + block.h + pad)
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 255
    return mask


def soft_rect_alpha(height: int, width: int, feather: int) -> np.ndarray:
    if height <= 0 or width <= 0:
        return np.zeros((0, 0), dtype=np.float32)
    if feather <= 0:
        return np.ones((height, width), dtype=np.float32)

    y = np.minimum(np.arange(height), np.arange(height)[::-1]).astype(np.float32)
    x = np.minimum(np.arange(width), np.arange(width)[::-1]).astype(np.float32)
    dist = np.minimum(y[:, None], x[None, :])
    alpha = np.clip((dist + 1.0) / float(feather + 1), 0.0, 1.0)
    return alpha.astype(np.float32)


def fit_background_plane(
    sample_x: np.ndarray,
    sample_y: np.ndarray,
    sample_rgb: np.ndarray,
    target_x: np.ndarray,
    target_y: np.ndarray,
    min_samples: int,
) -> tuple[np.ndarray, str]:
    if len(sample_rgb) < min_samples:
        fill = np.mean(sample_rgb, axis=0) if len(sample_rgb) else np.array([255, 255, 255], dtype=np.float32)
        return np.ones((*target_x.shape, 3), dtype=np.float32) * fill.reshape(1, 1, 3), "mean"

    design = np.stack([sample_x.astype(np.float32), sample_y.astype(np.float32), np.ones_like(sample_x, dtype=np.float32)], axis=1)
    target = np.stack([target_x.astype(np.float32), target_y.astype(np.float32), np.ones_like(target_x, dtype=np.float32)], axis=2)
    try:
        coeffs, *_ = np.linalg.lstsq(design, sample_rgb.astype(np.float32), rcond=None)
        patch = target @ coeffs
        lo = np.percentile(sample_rgb, 2, axis=0) - 8
        hi = np.percentile(sample_rgb, 98, axis=0) + 8
        patch = np.clip(patch, lo.reshape(1, 1, 3), hi.reshape(1, 1, 3))
        return patch.astype(np.float32), "plane"
    except np.linalg.LinAlgError:
        fill = np.mean(sample_rgb, axis=0)
        return np.ones((*target_x.shape, 3), dtype=np.float32) * fill.reshape(1, 1, 3), "mean"


def tile_plane_fill(
    image_rgb: np.ndarray,
    blocks: list[TextBlock],
    tile_size: int,
    box_pad: int,
    sample_radius: int,
    symbol_right_pad: int,
    feather_blur: int,
    seam_blur: int,
    min_samples: int,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    h, w = image_rgb.shape[:2]
    work = image_rgb.astype(np.float32).copy()
    all_box_mask = block_box_mask((h, w), blocks, box_pad, symbol_right_pad)
    all_text = all_box_mask > 0
    stats: list[dict[str, Any]] = []

    for block in blocks:
        right_pad = numeric_right_pad(block, box_pad, symbol_right_pad)
        bx0 = max(0, block.x - box_pad)
        by0 = max(0, block.y - box_pad)
        bx1 = min(w, block.x + block.w + right_pad)
        by1 = min(h, block.y + block.h + box_pad)
        if bx1 <= bx0 or by1 <= by0:
            continue

        fill_region = image_rgb[by0:by1, bx0:bx1].astype(np.float32).copy()
        tile_count = 0
        plane_count = 0

        for ty0 in range(by0, by1, tile_size):
            for tx0 in range(bx0, bx1, tile_size):
                tx1 = min(tx0 + tile_size, bx1)
                ty1 = min(ty0 + tile_size, by1)
                if tx1 <= tx0 or ty1 <= ty0:
                    continue

                sx0 = max(0, tx0 - sample_radius)
                sy0 = max(0, ty0 - sample_radius)
                sx1 = min(w, tx1 + sample_radius)
                sy1 = min(h, ty1 + sample_radius)
                sample_mask = np.ones((sy1 - sy0, sx1 - sx0), dtype=bool)
                sample_mask &= ~all_text[sy0:sy1, sx0:sx1]

                if int(sample_mask.sum()) < min_samples:
                    sx0 = max(0, bx0 - sample_radius * 2)
                    sy0 = max(0, by0 - sample_radius * 2)
                    sx1 = min(w, bx1 + sample_radius * 2)
                    sy1 = min(h, by1 + sample_radius * 2)
                    sample_mask = np.ones((sy1 - sy0, sx1 - sx0), dtype=bool)
                    sample_mask &= ~all_text[sy0:sy1, sx0:sx1]

                sample_ys, sample_xs = np.where(sample_mask)
                sample_rgb = image_rgb[sy0:sy1, sx0:sx1][sample_mask].astype(np.float32)
                sample_abs_x = sample_xs + sx0
                sample_abs_y = sample_ys + sy0

                target_x, target_y = np.meshgrid(np.arange(tx0, tx1), np.arange(ty0, ty1))
                patch, method = fit_background_plane(
                    sample_abs_x,
                    sample_abs_y,
                    sample_rgb,
                    target_x,
                    target_y,
                    min_samples=min_samples,
                )
                fill_region[ty0 - by0 : ty1 - by0, tx0 - bx0 : tx1 - bx0] = patch
                tile_count += 1
                plane_count += int(method == "plane")

        if seam_blur > 0:
            k = seam_blur * 2 + 1
            if k % 2 == 0:
                k += 1
            fill_region = cv2.GaussianBlur(fill_region, (k, k), 0)

        alpha_2d = soft_rect_alpha(by1 - by0, bx1 - bx0, feather_blur)
        if feather_blur > 0 and by1 - by0 > feather_blur * 2 and bx1 - bx0 > feather_blur * 2:
            alpha_2d[feather_blur : by1 - by0 - feather_blur, feather_blur : bx1 - bx0 - feather_blur] = 1.0
        original_x0 = max(0, block.x) - bx0
        original_y0 = max(0, block.y) - by0
        original_x1 = min(w, block.x + block.w) - bx0
        original_y1 = min(h, block.y + block.h) - by0
        alpha_2d[original_y0:original_y1, original_x0:original_x1] = 1.0
        alpha = alpha_2d[..., None]
        work[by0:by1, bx0:bx1] = fill_region * alpha + work[by0:by1, bx0:bx1] * (1.0 - alpha)
        stats.append(
            {
                "bbox": [bx0, by0, bx1 - bx0, by1 - by0],
                "tiles": tile_count,
                "plane_tiles": plane_count,
            }
        )

    return np.clip(work, 0, 255).astype(np.uint8), all_box_mask, stats


def save_mask_preview(path: Path, image_rgb: np.ndarray, mask: np.ndarray, blocks: list[TextBlock]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = Image.fromarray(image_rgb).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    red = Image.new("RGBA", base.size, (255, 0, 0, 105))
    mask_img = Image.fromarray(mask, "L")
    overlay = Image.composite(red, overlay, mask_img)
    composed = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)
    for block in blocks:
        draw.rectangle([block.x, block.y, block.x + block.w, block.y + block.h], outline=(0, 0, 255), width=2)
    composed.save(path, quality=94)


def make_contact_sheet(
    output_root: Path,
    image_path: Path,
    images: list[tuple[str, Path]],
    thumb_width: int,
    cols: int,
) -> Path:
    cells: list[tuple[str, Image.Image]] = [("original", Image.open(image_path).convert("RGB"))]
    for label, path in images:
        if path.exists():
            cells.append((label, Image.open(path).convert("RGB")))

    original = cells[0][1]
    thumb_h = round(original.height * thumb_width / original.width)
    gap = max(10, thumb_width // 80)
    header_h = max(36, thumb_width // 24)
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_width + (cols + 1) * gap, rows * (thumb_h + header_h) + (rows + 1) * gap), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", max(16, thumb_width // 42))
    except Exception:
        font = ImageFont.load_default()

    for idx, (label, image) in enumerate(cells):
        x = gap + (idx % cols) * (thumb_width + gap)
        y = gap + (idx // cols) * (thumb_h + header_h + gap)
        draw.text((x, y), label, fill=(20, 20, 20), font=font)
        sheet.paste(image.resize((thumb_width, thumb_h), Image.Resampling.LANCZOS), (x, y + header_h))

    path = output_root / "contact-sheets" / f"{image_path.stem}__local_mean_fill.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=94)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="test-materials/input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--mode", default="pixel-components", choices=["pixel-components", "tile-plane"])
    parser.add_argument("--min-diff", type=float, default=24.0)
    parser.add_argument("--mask-dilate", type=int, default=1)
    parser.add_argument("--tile-size", type=int, default=24)
    parser.add_argument("--box-pad", type=int, default=12)
    parser.add_argument("--sample-radius", type=int, default=14)
    parser.add_argument("--symbol-right-pad", type=int, default=52)
    parser.add_argument("--cover-dilate", type=int, default=2)
    parser.add_argument("--feather-blur", type=int, default=5)
    parser.add_argument("--seam-blur", type=int, default=1)
    parser.add_argument("--min-samples", type=int, default=32)
    parser.add_argument("--min-component-area", type=int, default=3)
    parser.add_argument("--include-baselines", action="store_true")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument("--contact-thumb-width", type=int, default=760)
    parser.add_argument("--contact-cols", type=int, default=2)
    args = parser.parse_args()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_dir).resolve() if args.output_dir else Path("test-materials/output/local-mean-fill").resolve() / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    input_dir = Path(args.input_dir).resolve()
    inputs = load_inputs(input_dir, args.limit)
    if not inputs:
        raise SystemExit(f"No input images found in {input_dir}")

    manifest: dict[str, Any] = {
        "created_at": timestamp,
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "parameters": vars(args),
        "runs": [],
    }

    ocr_cache = output_root / "ocr"
    for image_path in inputs:
        started = time.time()
        image_rgb = np.array(Image.open(image_path).convert("RGB"))
        blocks = get_or_detect_blocks(image_path, ocr_cache, force_ocr=args.force_ocr)
        if args.mode == "tile-plane":
            filled, mask, components = tile_plane_fill(
                image_rgb,
                blocks,
                tile_size=args.tile_size,
                box_pad=args.box_pad,
                sample_radius=args.sample_radius,
                symbol_right_pad=args.symbol_right_pad,
                feather_blur=args.feather_blur,
                seam_blur=args.seam_blur,
                min_samples=args.min_samples,
            )
            fill_label = f"tile plane fill {args.tile_size}px"
            fill_dir = "tile_plane_fill"
            mask_label = "ocr box tile mask"
        else:
            mask = build_text_pixel_mask(image_rgb, blocks, min_diff=args.min_diff, mask_dilate=args.mask_dilate)
            filled, components = local_mean_fill(
                image_rgb,
                mask,
                sample_radius=args.sample_radius,
                cover_dilate=args.cover_dilate,
                feather_blur=args.feather_blur,
                min_component_area=args.min_component_area,
            )
            fill_label = "local mean fill"
            fill_dir = "local_mean_fill"
            mask_label = "text pixel mask"

        local_path = output_root / fill_dir / f"{image_path.stem}.png"
        mask_path = output_root / "masks" / f"{image_path.stem}__mask.png"
        mask_preview_path = output_root / "masks" / f"{image_path.stem}__mask_preview.jpg"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(filled).save(local_path)
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(mask).save(mask_path)
        save_mask_preview(mask_preview_path, image_rgb, mask, blocks)

        sheet_inputs: list[tuple[str, Path]] = [
            (mask_label, mask_preview_path),
            (fill_label, local_path),
        ]

        baseline_paths: dict[str, str] = {}
        if args.include_baselines and blocks:
            lama_path = output_root / "torch_lama_default" / f"{image_path.stem}.png"
            lama_path.parent.mkdir(parents=True, exist_ok=True)
            lama = remove_text_from_image(str(image_path), blocks, device=args.device)
            lama.save(lama_path)
            baseline_paths["torch_lama_default"] = str(lama_path)
            sheet_inputs.append(("torch lama default", lama_path))

            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            box_mask = np.zeros(mask.shape, dtype=np.uint8)
            for block in blocks:
                box_mask[block.y : block.y + block.h, block.x : block.x + block.w] = 255
            opencv = cv2.inpaint(image_bgr, box_mask, 3, cv2.INPAINT_TELEA)
            opencv_path = output_root / "opencv_telea_box" / f"{image_path.stem}.png"
            opencv_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(cv2.cvtColor(opencv, cv2.COLOR_BGR2RGB)).save(opencv_path)
            baseline_paths["opencv_telea_box"] = str(opencv_path)
            sheet_inputs.append(("opencv telea box", opencv_path))

        sheet_path = make_contact_sheet(output_root, image_path, sheet_inputs, args.contact_thumb_width, args.contact_cols)

        row = {
            "image": str(image_path),
            "seconds": round(time.time() - started, 3),
            "text_blocks": len(blocks),
            "mask_pixels": int((mask > 0).sum()),
            "components": len(components),
            "component_area_min": min((c.get("area", 0) for c in components), default=0),
            "component_area_max": max((c.get("area", 0) for c in components), default=0),
            "tiles": sum((c.get("tiles", 0) for c in components), 0),
            "plane_tiles": sum((c.get("plane_tiles", 0) for c in components), 0),
            "output": str(local_path),
            "mask": str(mask_path),
            "mask_preview": str(mask_preview_path),
            "contact_sheet": str(sheet_path),
            "baselines": baseline_paths,
        }
        manifest["runs"].append(row)
        tile_part = f" | tiles={row['tiles']}" if args.mode == "tile-plane" else ""
        print(f"{image_path.name} | blocks={len(blocks)} | components={len(components)}{tile_part} | mask_px={row['mask_pixels']} | {row['seconds']}s", flush=True)

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
