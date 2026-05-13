#!/usr/bin/env python3
"""
Screen segmented DeckLens layers for vectorization suitability.

This is a local research script only. It does not integrate with the app.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class CandidateScore:
    image: str
    mask_key: str
    cutout: str
    bbox: list[int]
    area: int
    area_ratio: float
    dominant_color_count: int
    dominant_colors_rgb: list[list[int]]
    foreground_color_count: int
    foreground_ratio: float
    color_entropy: float
    edge_density: float
    palette_error_mean: float
    palette_error_p95: float
    rectangle_score: float
    circle_score: float
    solidity: float
    bbox_extent: float
    circularity: float
    approx_vertices: int
    shape_label: str
    vector_score: float
    candidate_tier: str
    reason: str


def parse_args() -> argparse.Namespace:
    default_run = Path("test-materials/output/layering-research/20260513-clean-lama-model-comparison")
    return argparse.ArgumentParser(description=__doc__).parse_args()


def build_parser() -> argparse.ArgumentParser:
    default_run = Path("test-materials/output/layering-research/20260513-clean-lama-model-comparison")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("test-materials/output/layering-clean-inputs/20260513-lama-text-removed/clean-backgrounds"),
        help="Directory containing clean background images.",
    )
    parser.add_argument(
        "--mask-dir",
        type=Path,
        default=default_run / "masks" / "fastsam_s",
        help="Directory containing .npz masks named like the input image stem.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test-materials/output/vectorization-candidates")
        / datetime.now().strftime("%Y%m%d-%H%M%S"),
        help="Output directory for candidate crops and reports.",
    )
    parser.add_argument("--max-colors", type=int, default=10)
    parser.add_argument(
        "--color-min-ratio",
        type=float,
        default=0.002,
        help="Minimum pixel ratio for a quantized color bucket to count as part of the palette.",
    )
    parser.add_argument("--min-area-ratio", type=float, default=0.0008)
    parser.add_argument("--max-area-ratio", type=float, default=0.25)
    parser.add_argument("--contact-sheet-limit", type=int, default=80)
    return parser


def iter_images(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() in IMAGE_EXTS:
            yield path


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def dominant_colors(image_rgb: np.ndarray, mask: np.ndarray, min_ratio: float) -> tuple[int, list[list[int]]]:
    pixels = image_rgb[mask]
    if len(pixels) == 0:
        return 0, []

    if len(pixels) > 60000:
        idx = np.linspace(0, len(pixels) - 1, 60000).astype(np.int64)
        pixels = pixels[idx]

    # Bucket to 4 bits/channel to make anti-aliased edges and tiny JPEG noise irrelevant.
    buckets = (pixels.astype(np.uint16) // 16).astype(np.uint8)
    unique, counts = np.unique(buckets, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    min_cluster = max(8, int(len(pixels) * min_ratio))

    dominant = []
    for i in order:
        if counts[i] < min_cluster:
            continue
        bucket_pixels = pixels[np.all(buckets == unique[i], axis=1)]
        color = np.median(bucket_pixels, axis=0).astype(int).tolist()
        dominant.append(color)

    if not dominant and len(order):
        bucket_pixels = pixels[np.all(buckets == unique[order[0]], axis=1)]
        dominant.append(np.median(bucket_pixels, axis=0).astype(int).tolist())
    return len(dominant), dominant[:12]


def foreground_mask(image_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Remove near-white/near-neutral page or card background before color complexity checks."""
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    near_white = ((val >= 238) & (sat <= 32)) | np.all(image_rgb >= 246, axis=2)
    return mask & ~near_white


def color_complexity(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    min_ratio: float,
    bucket_size: int = 8,
) -> tuple[int, float, list[list[int]]]:
    pixels = image_rgb[mask]
    if len(pixels) == 0:
        return 0, 0.0, []
    if len(pixels) > 80000:
        idx = np.linspace(0, len(pixels) - 1, 80000).astype(np.int64)
        pixels = pixels[idx]

    buckets = (pixels.astype(np.uint16) // bucket_size).astype(np.uint8)
    unique, counts = np.unique(buckets, axis=0, return_counts=True)
    min_cluster = max(4, int(len(pixels) * min_ratio))
    kept = counts >= min_cluster
    if not np.any(kept):
        kept[np.argmax(counts)] = True

    kept_counts = counts[kept]
    probs = kept_counts.astype(np.float64) / max(float(kept_counts.sum()), 1.0)
    entropy = float(-(probs * np.log2(probs)).sum())

    order = np.argsort(counts[kept])[::-1]
    kept_unique = unique[kept]
    top = []
    for i in order[:12]:
        bucket_pixels = pixels[np.all(buckets == kept_unique[i], axis=1)]
        top.append(np.median(bucket_pixels, axis=0).astype(int).tolist())
    return int(kept.sum()), round(entropy, 3), top


def palette_reconstruction_error(image_rgb: np.ndarray, mask: np.ndarray, k: int) -> tuple[float, float]:
    pixels = image_rgb[mask]
    if len(pixels) == 0:
        return 0.0, 0.0
    if len(pixels) > 50000:
        idx = np.linspace(0, len(pixels) - 1, 50000).astype(np.int64)
        pixels = pixels[idx]

    lab = cv2.cvtColor(pixels.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    unique_count = len(np.unique(lab, axis=0))
    cluster_count = min(k, unique_count, len(lab))
    if cluster_count <= 1:
        return 0.0, 0.0

    samples = lab.astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _compactness, labels, centers = cv2.kmeans(
        samples,
        cluster_count,
        None,
        criteria,
        2,
        cv2.KMEANS_PP_CENTERS,
    )
    reconstructed = centers[labels.reshape(-1)]
    err = np.linalg.norm(samples - reconstructed, axis=1)
    return round(float(np.mean(err)), 3), round(float(np.percentile(err, 95)), 3)


def edge_density(image_rgb: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    x0, y0, x1, y1 = mask_bbox(mask)
    gray_crop = gray[y0:y1, x0:x1]
    mask_crop = mask[y0:y1, x0:x1]
    edges = cv2.Canny(gray_crop, 40, 120)
    return round(float(((edges > 0) & mask_crop).sum() / max(mask_crop.sum(), 1)), 4)


def largest_contour(mask_crop: np.ndarray):
    contours, _ = cv2.findContours(mask_crop.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def shape_metrics(mask_crop: np.ndarray) -> dict:
    area = float(mask_crop.sum())
    h, w = mask_crop.shape[:2]
    contour = largest_contour(mask_crop)
    if contour is None or area <= 0:
        return {
            "rectangle_score": 0.0,
            "circle_score": 0.0,
            "solidity": 0.0,
            "bbox_extent": 0.0,
            "circularity": 0.0,
            "approx_vertices": 0,
            "shape_label": "empty",
        }

    perimeter = max(float(cv2.arcLength(contour, True)), 1.0)
    contour_area = max(float(cv2.contourArea(contour)), area)
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    solidity = min(1.0, contour_area / hull_area)
    bbox_extent = min(1.0, area / max(float(w * h), 1.0))
    circularity = min(1.0, 4.0 * math.pi * contour_area / (perimeter * perimeter))

    epsilon = 0.025 * perimeter
    approx = cv2.approxPolyDP(contour, epsilon, True)
    approx_vertices = int(len(approx))
    aspect = w / max(h, 1)

    rect_score = 0.0
    if 0.15 <= aspect <= 6.5:
        rect_score = 0.55 * bbox_extent + 0.35 * solidity + 0.10 * max(0.0, 1.0 - min(abs(approx_vertices - 4), 8) / 8)
        if bbox_extent > 0.82 and solidity > 0.9:
            rect_score = max(rect_score, 0.92)

    circle_aspect_score = max(0.0, 1.0 - abs(aspect - 1.0) / 0.35)
    circle_score = 0.55 * circularity + 0.25 * circle_aspect_score + 0.20 * solidity
    if 0.78 <= aspect <= 1.28 and circularity > 0.72 and solidity > 0.88:
        circle_score = max(circle_score, 0.90)

    if rect_score >= 0.82:
        label = "rect_or_round_rect"
    elif circle_score >= 0.82:
        label = "circle_or_ellipse"
    elif approx_vertices <= 10 and solidity >= 0.82:
        label = "simple_polygon"
    else:
        label = "complex"

    return {
        "rectangle_score": round(float(rect_score), 3),
        "circle_score": round(float(circle_score), 3),
        "solidity": round(float(solidity), 3),
        "bbox_extent": round(float(bbox_extent), 3),
        "circularity": round(float(circularity), 3),
        "approx_vertices": approx_vertices,
        "shape_label": label,
    }


def save_cutout(image_rgb: np.ndarray, mask: np.ndarray, bbox: tuple[int, int, int, int], out_path: Path) -> None:
    x0, y0, x1, y1 = bbox
    crop_rgb = image_rgb[y0:y1, x0:x1]
    crop_mask = mask[y0:y1, x0:x1]
    rgba = np.zeros((crop_rgb.shape[0], crop_rgb.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = crop_rgb
    rgba[:, :, 3] = (crop_mask.astype(np.uint8) * 255)
    Image.fromarray(rgba, "RGBA").save(out_path)


def screen_mask(
    image_path: Path,
    image_rgb: np.ndarray,
    mask_key: str,
    mask: np.ndarray,
    out_dir: Path,
    max_colors: int,
    color_min_ratio: float,
    min_area_ratio: float,
    max_area_ratio: float,
) -> CandidateScore | None:
    mask = mask.astype(bool)
    area = int(mask.sum())
    total_area = int(mask.shape[0] * mask.shape[1])
    area_ratio = area / max(total_area, 1)
    if area_ratio < min_area_ratio or area_ratio > max_area_ratio:
        return None

    bbox = mask_bbox(mask)
    x0, y0, x1, y1 = bbox
    if (x1 - x0) < 8 or (y1 - y0) < 8:
        return None

    color_count, colors = dominant_colors(image_rgb, mask, color_min_ratio)
    fg_mask = foreground_mask(image_rgb, mask)
    fg_ratio = float(fg_mask.sum() / max(mask.sum(), 1))
    fg_color_count, color_entropy, fg_colors = color_complexity(image_rgb, fg_mask, color_min_ratio)
    palette_mean, palette_p95 = palette_reconstruction_error(
        image_rgb,
        fg_mask if fg_ratio >= 0.02 else mask,
        max_colors,
    )
    complexity_color_count = fg_color_count if fg_ratio >= 0.02 else color_count
    color_sample = fg_colors if fg_ratio >= 0.02 else colors
    texture_edges = edge_density(image_rgb, fg_mask if fg_ratio >= 0.02 else mask)
    shape = shape_metrics(mask[y0:y1, x0:x1])
    shape_score = max(shape["rectangle_score"], shape["circle_score"])
    if shape["shape_label"] == "simple_polygon":
        shape_score = max(shape_score, 0.72)

    color_score = max(0.0, min(1.0, (max_colors + 2 - complexity_color_count) / (max_colors + 1)))
    vector_score = round(float(0.52 * color_score + 0.48 * shape_score), 3)
    low_palette_error = palette_mean <= 7.0 and palette_p95 <= 20.0
    low_complexity = (
        complexity_color_count <= max_colors
        and color_entropy <= 2.0
        and texture_edges <= 0.18
    )
    flat_icon_like = (
        fg_ratio >= 0.02
        and complexity_color_count <= max(32, max_colors)
        and color_entropy <= 4.6
        and texture_edges <= 0.32
        and low_palette_error
    )
    likely_gradient_or_3d = fg_ratio >= 0.02 and (
        palette_mean > 9.0
        or palette_p95 > 28.0
        or color_entropy > 5.2
        or texture_edges > 0.34
    )

    if (
        (low_complexity or flat_icon_like)
        and shape["shape_label"] in {"rect_or_round_rect", "circle_or_ellipse"}
        and vector_score >= 0.65
    ):
        tier = "strong"
        reason = "low_color_basic_shape" if low_complexity else "flat_icon_palette_fits"
    elif (low_complexity or flat_icon_like) and shape["shape_label"] in {
        "rect_or_round_rect",
        "circle_or_ellipse",
        "simple_polygon",
    }:
        tier = "review"
        reason = "low_color_shape_needs_review" if low_complexity else "flat_icon_palette_needs_review"
    elif (low_complexity or flat_icon_like) and vector_score >= 0.70:
        tier = "review"
        reason = "low_color_shape_score_borderline" if low_complexity else "flat_icon_score_borderline"
    elif likely_gradient_or_3d:
        tier = "reject"
        reason = "foreground_too_many_colors_or_gradient"
    else:
        tier = "reject"
        reason = "too_many_colors_or_complex_shape"

    safe_stem = image_path.stem.replace("/", "_")
    cutout_name = f"{safe_stem}__{mask_key}__{tier}.png"
    cutout_path = out_dir / "cutouts" / cutout_name
    save_cutout(image_rgb, mask, bbox, cutout_path)

    return CandidateScore(
        image=str(image_path),
        mask_key=mask_key,
        cutout=str(cutout_path),
        bbox=[x0, y0, x1 - x0, y1 - y0],
        area=area,
        area_ratio=round(area_ratio, 5),
        dominant_color_count=int(color_count),
        dominant_colors_rgb=color_sample,
        foreground_color_count=int(fg_color_count),
        foreground_ratio=round(fg_ratio, 4),
        color_entropy=float(color_entropy),
        edge_density=float(texture_edges),
        palette_error_mean=float(palette_mean),
        palette_error_p95=float(palette_p95),
        rectangle_score=shape["rectangle_score"],
        circle_score=shape["circle_score"],
        solidity=shape["solidity"],
        bbox_extent=shape["bbox_extent"],
        circularity=shape["circularity"],
        approx_vertices=shape["approx_vertices"],
        shape_label=shape["shape_label"],
        vector_score=vector_score,
        candidate_tier=tier,
        reason=reason,
    )


def write_contact_sheet(scores: list[CandidateScore], output_path: Path, limit: int) -> None:
    selected = [s for s in scores if s.candidate_tier in {"strong", "review"}]
    selected.sort(key=lambda s: (s.candidate_tier != "strong", -s.vector_score, s.dominant_color_count))
    selected = selected[:limit]
    if not selected:
        return

    tile_w, tile_h = 260, 210
    cols = 4
    rows = math.ceil(len(selected) / cols)
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("Arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    for idx, score in enumerate(selected):
        x = (idx % cols) * tile_w
        y = (idx // cols) * tile_h
        cutout = Image.open(score.cutout).convert("RGBA")
        cutout.thumbnail((tile_w - 24, tile_h - 70), Image.Resampling.LANCZOS)
        bg = Image.new("RGBA", cutout.size, (245, 245, 245, 255))
        bg.alpha_composite(cutout)
        px = x + (tile_w - bg.width) // 2
        py = y + 8
        sheet.paste(bg.convert("RGB"), (px, py))

        label = (
            f"{score.candidate_tier} {score.vector_score:.2f} "
            f"{score.shape_label} fg={score.foreground_color_count} err={score.palette_error_mean:.1f}"
        )
        draw.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline=(220, 220, 220))
        draw.text((x + 8, y + tile_h - 54), Path(score.image).stem[:34], fill=(20, 20, 20), font=font)
        draw.text((x + 8, y + tile_h - 36), score.mask_key, fill=(70, 70, 70), font=font)
        draw.text((x + 8, y + tile_h - 18), label, fill=(0, 0, 0), font=font)

    sheet.save(output_path, quality=92)


def write_summary(scores: list[CandidateScore], output_dir: Path) -> None:
    strong = [s for s in scores if s.candidate_tier == "strong"]
    review = [s for s in scores if s.candidate_tier == "review"]
    reject = [s for s in scores if s.candidate_tier == "reject"]
    lines = [
        "# Vectorization Candidate Screening",
        "",
        f"- total masks scored: {len(scores)}",
        f"- strong candidates: {len(strong)}",
        f"- review candidates: {len(review)}",
        f"- rejected: {len(reject)}",
        "",
        "## Top candidates",
        "",
        "| tier | score | image | mask | shape | colors | fg colors | entropy | palette err | bbox | cutout |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    top = sorted(scores, key=lambda s: (s.candidate_tier == "reject", -s.vector_score))[:40]
    for s in top:
        cutout_rel = Path(s.cutout).relative_to(output_dir)
        lines.append(
            f"| {s.candidate_tier} | {s.vector_score:.2f} | {Path(s.image).name} | {s.mask_key} | "
            f"{s.shape_label} | {s.dominant_color_count} | {s.foreground_color_count} | "
            f"{s.color_entropy:.2f} | {s.palette_error_mean:.2f}/{s.palette_error_p95:.2f} | "
            f"{s.bbox} | {cutout_rel} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    output_dir: Path = args.output_dir
    (output_dir / "cutouts").mkdir(parents=True, exist_ok=True)

    all_scores: list[CandidateScore] = []
    missing_masks = []
    for image_path in iter_images(args.input_dir):
        mask_path = args.mask_dir / f"{image_path.stem}.npz"
        if not mask_path.exists():
            missing_masks.append(str(mask_path))
            continue

        image_rgb = np.array(Image.open(image_path).convert("RGB"))
        with np.load(mask_path) as masks:
            for mask_key in masks.files:
                score = screen_mask(
                    image_path=image_path,
                    image_rgb=image_rgb,
                    mask_key=mask_key,
                    mask=masks[mask_key],
                    out_dir=output_dir,
                    max_colors=args.max_colors,
                    color_min_ratio=args.color_min_ratio,
                    min_area_ratio=args.min_area_ratio,
                    max_area_ratio=args.max_area_ratio,
                )
                if score is not None:
                    all_scores.append(score)

    all_scores.sort(key=lambda s: (s.candidate_tier == "reject", -s.vector_score, s.dominant_color_count))
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(args.input_dir),
        "mask_dir": str(args.mask_dir),
        "output_dir": str(output_dir),
        "parameters": {
            "max_colors": args.max_colors,
            "color_min_ratio": args.color_min_ratio,
            "min_area_ratio": args.min_area_ratio,
            "max_area_ratio": args.max_area_ratio,
        },
        "missing_masks": missing_masks,
        "scores": [asdict(s) for s in all_scores],
    }
    (output_dir / "candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(all_scores, output_dir)
    write_contact_sheet(all_scores, output_dir / "contact_sheet.jpg", args.contact_sheet_limit)

    strong = sum(1 for s in all_scores if s.candidate_tier == "strong")
    review = sum(1 for s in all_scores if s.candidate_tier == "review")
    print(f"scored={len(all_scores)} strong={strong} review={review} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
