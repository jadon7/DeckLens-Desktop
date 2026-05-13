#!/usr/bin/env python3
"""
Run local segmentation/layering experiments for DeckLens PPT-like images.

This is intentionally outside the product path. It compares:
- existing OpenCV color/connected-component fallback
- legacy Segment Anything (if a checkpoint is already present, or download is explicitly enabled)
- Ultralytics YOLO segmentation
- Ultralytics FastSAM

Outputs are written under test-materials/output/layering-research by default.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import (  # noqa: E402
    _is_sam_checkpoint_complete,
    _sam_model_config,
    get_sam_mask_generator,
    segment_background_cv_masks,
)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Algorithm:
    name: str
    factory: Callable[[], Callable[[np.ndarray], list[dict[str, Any]]]]
    setup: dict[str, Any]


def load_inputs(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def bbox_from_mask(seg: np.ndarray) -> list[int]:
    ys, xs = np.where(seg)
    if len(xs) == 0 or len(ys) == 0:
        return [0, 0, 0, 0]
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max())
    y1 = int(ys.max())
    return [x0, y0, x1 - x0 + 1, y1 - y0 + 1]


def normalize_mask(mask: np.ndarray, shape: tuple[int, int], threshold: float = 0.5) -> np.ndarray:
    h, w = shape
    arr = np.asarray(mask)
    if arr.shape[:2] != (h, w):
        arr = cv2.resize(arr.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
    if arr.dtype == bool:
        return arr
    return arr.astype(np.float32) > threshold


def post_process_masks(
    image_rgb: np.ndarray,
    masks: list[dict[str, Any]],
    min_area_ratio: float,
    max_area_ratio: float,
    bg_color_threshold: float,
    overlap_iou_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    img_h, img_w = image_rgb.shape[:2]
    total_area = img_h * img_w

    area_filtered = []
    for mask in masks:
        seg = normalize_mask(mask["segmentation"], (img_h, img_w))
        area = int(seg.sum())
        if area <= 0:
            continue
        area_ratio = area / total_area
        if min_area_ratio <= area_ratio <= max_area_ratio:
            normalized = dict(mask)
            normalized["segmentation"] = seg
            normalized["area"] = area
            normalized["bbox"] = [int(v) for v in normalized.get("bbox") or bbox_from_mask(seg)]
            area_filtered.append(normalized)

    corner_size = max(20, min(img_w, img_h) // 10)
    corners = np.concatenate(
        [
            image_rgb[:corner_size, :corner_size].reshape(-1, 3),
            image_rgb[:corner_size, -corner_size:].reshape(-1, 3),
            image_rgb[-corner_size:, :corner_size].reshape(-1, 3),
            image_rgb[-corner_size:, -corner_size:].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_color = np.median(corners, axis=0)

    color_filtered = []
    for mask in area_filtered:
        seg = mask["segmentation"]
        mean_color = np.mean(image_rgb[seg], axis=0)
        color_diff = float(np.sqrt(np.sum((mean_color - bg_color) ** 2)))
        if color_diff >= bg_color_threshold:
            normalized = dict(mask)
            normalized["color_diff"] = round(color_diff, 3)
            color_filtered.append(normalized)

    color_filtered.sort(key=lambda item: item["area"], reverse=True)
    keep = []
    for mask in color_filtered:
        should_keep = True
        seg_m = mask["segmentation"]
        for kept in keep:
            seg_k = kept["segmentation"]
            intersection = int(np.logical_and(seg_m, seg_k).sum())
            union = int(np.logical_or(seg_m, seg_k).sum())
            if union > 0 and intersection / union > overlap_iou_threshold:
                should_keep = False
                break
        if should_keep:
            keep.append(mask)

    stats = {
        "raw": len(masks),
        "area_filtered": len(area_filtered),
        "color_filtered": len(color_filtered),
        "kept": len(keep),
        "bg_color_rgb": [round(float(v), 2) for v in bg_color],
    }
    return keep, stats


def summarize_masks(masks: list[dict[str, Any]], total_area: int) -> dict[str, Any]:
    areas = [int(mask["area"]) for mask in masks]
    coverage = float(sum(areas) / total_area) if total_area else 0.0
    return {
        "count": len(masks),
        "coverage_ratio": round(coverage, 4),
        "area_ratio_min": round(min(areas) / total_area, 4) if areas else 0.0,
        "area_ratio_median": round(statistics.median(areas) / total_area, 4) if areas else 0.0,
        "area_ratio_max": round(max(areas) / total_area, 4) if areas else 0.0,
        "bbox": [
            {
                "area_ratio": round(mask["area"] / total_area, 4),
                "bbox": [int(v) for v in mask["bbox"]],
                "label": mask.get("label"),
                "score": mask.get("score"),
            }
            for mask in masks
        ],
    }


def save_masks_npz(path: Path, masks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {f"mask_{idx:03d}": mask["segmentation"].astype(np.uint8) for idx, mask in enumerate(masks)}
    np.savez_compressed(path, **arrays)


def save_overlay(path: Path, image_rgb: np.ndarray, masks: list[dict[str, Any]], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = Image.fromarray(image_rgb).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    palette = [
        (230, 57, 70, 105),
        (29, 117, 208, 105),
        (42, 157, 143, 105),
        (245, 158, 11, 105),
        (123, 63, 228, 105),
        (214, 40, 40, 105),
        (38, 70, 83, 105),
        (46, 204, 113, 105),
    ]
    for idx, mask in enumerate(masks):
        seg = mask["segmentation"]
        mask_img = Image.fromarray((seg * 255).astype(np.uint8), mode="L")
        color = Image.new("RGBA", base.size, palette[idx % len(palette)])
        overlay = Image.composite(color, overlay, mask_img)
    composed = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except Exception:
        font = ImageFont.load_default()
        small_font = font

    draw.rectangle([0, 0, composed.width, 34], fill=(255, 255, 255))
    draw.text((10, 6), title, fill=(20, 20, 20), font=small_font)
    for idx, mask in enumerate(masks):
        x, y, w, h = [int(v) for v in mask["bbox"]]
        draw.rectangle([x, y, x + w, y + h], outline=(255, 255, 255), width=3)
        draw.rectangle([x, y, x + w, y + h], outline=(20, 20, 20), width=1)
        label = str(idx + 1)
        tb = draw.textbbox((x, y), label, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.rectangle([x, y, x + tw + 8, y + th + 6], fill=(255, 255, 255))
        draw.text((x + 4, y + 3), label, fill=(0, 0, 0), font=font)
    composed.save(path, quality=95)


def create_contact_sheet(
    image_path: Path,
    output_root: Path,
    overlays: list[tuple[str, Path]],
    thumb_width: int,
    cols: int,
) -> Path:
    original = Image.open(image_path).convert("RGB")
    items: list[tuple[str, Image.Image]] = [("original", original)]
    for label, overlay_path in overlays:
        if overlay_path.exists():
            items.append((label, Image.open(overlay_path).convert("RGB")))

    thumb_h = round(original.height * thumb_width / original.width)
    header_h = max(38, thumb_width // 20)
    gap = max(10, thumb_width // 80)
    cols = max(1, cols)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_width + (cols + 1) * gap, rows * (thumb_h + header_h) + (rows + 1) * gap), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(16, thumb_width // 38))
    except Exception:
        font = ImageFont.load_default()

    for idx, (label, image) in enumerate(items):
        x = gap + (idx % cols) * (thumb_width + gap)
        y = gap + (idx // cols) * (thumb_h + header_h + gap)
        draw.text((x, y), label, fill=(20, 20, 20), font=font)
        thumb = image.resize((thumb_width, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y + header_h))

    path = output_root / "contact-sheets" / f"{image_path.stem}__segmentation_comparison.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=94)
    return path


def cv_fallback_factory() -> Callable[[np.ndarray], list[dict[str, Any]]]:
    def run(image_rgb: np.ndarray) -> list[dict[str, Any]]:
        return segment_background_cv_masks(image_rgb, min_area_ratio=0.0005, max_area_ratio=0.95, bg_color_threshold=25.0)

    return run


def sam_factory(device: str) -> Callable[[np.ndarray], list[dict[str, Any]]]:
    os.environ["DECKLENS_ENABLE_SAM"] = "1"
    os.environ.setdefault("DECKLENS_SAM_POINTS_PER_SIDE", "16")
    generator = get_sam_mask_generator(device)

    def run(image_rgb: np.ndarray) -> list[dict[str, Any]]:
        return generator.generate(image_rgb)

    return run


def yolo_seg_factory(weights: str, imgsz: int, conf: float) -> Callable[[np.ndarray], list[dict[str, Any]]]:
    from ultralytics import YOLO

    model = YOLO(weights)

    def run(image_rgb: np.ndarray) -> list[dict[str, Any]]:
        result = model.predict(image_rgb, imgsz=imgsz, conf=conf, retina_masks=True, verbose=False)[0]
        if result.masks is None:
            return []
        names = result.names
        classes = result.boxes.cls.cpu().numpy().astype(int) if result.boxes is not None else []
        scores = result.boxes.conf.cpu().numpy().tolist() if result.boxes is not None else []
        boxes = result.boxes.xyxy.cpu().numpy().tolist() if result.boxes is not None else []
        masks = result.masks.data.cpu().numpy()
        out = []
        for idx, seg in enumerate(masks):
            bool_seg = normalize_mask(seg, image_rgb.shape[:2])
            x0, y0, x1, y1 = boxes[idx] if idx < len(boxes) else [*bbox_from_mask(bool_seg)[:2], 0, 0]
            if idx >= len(boxes):
                bbox = bbox_from_mask(bool_seg)
            else:
                bbox = [int(round(x0)), int(round(y0)), int(round(x1 - x0)), int(round(y1 - y0))]
            class_id = int(classes[idx]) if idx < len(classes) else None
            out.append(
                {
                    "segmentation": bool_seg,
                    "area": int(bool_seg.sum()),
                    "bbox": bbox,
                    "label": names.get(class_id, str(class_id)) if class_id is not None else None,
                    "score": round(float(scores[idx]), 4) if idx < len(scores) else None,
                }
            )
        return out

    return run


def fastsam_factory(weights: str, imgsz: int, conf: float) -> Callable[[np.ndarray], list[dict[str, Any]]]:
    from ultralytics import FastSAM

    model = FastSAM(weights)

    def run(image_rgb: np.ndarray) -> list[dict[str, Any]]:
        result = model.predict(image_rgb, imgsz=imgsz, conf=conf, retina_masks=True, verbose=False)[0]
        if result.masks is None:
            return []
        scores = result.boxes.conf.cpu().numpy().tolist() if result.boxes is not None else []
        boxes = result.boxes.xyxy.cpu().numpy().tolist() if result.boxes is not None else []
        masks = result.masks.data.cpu().numpy()
        out = []
        for idx, seg in enumerate(masks):
            bool_seg = normalize_mask(seg, image_rgb.shape[:2])
            if idx < len(boxes):
                x0, y0, x1, y1 = boxes[idx]
                bbox = [int(round(x0)), int(round(y0)), int(round(x1 - x0)), int(round(y1 - y0))]
            else:
                bbox = bbox_from_mask(bool_seg)
            out.append(
                {
                    "segmentation": bool_seg,
                    "area": int(bool_seg.sum()),
                    "bbox": bbox,
                    "label": "fastsam",
                    "score": round(float(scores[idx]), 4) if idx < len(scores) else None,
                }
            )
        return out

    return run


def build_algorithms(args: argparse.Namespace) -> list[Algorithm]:
    algorithms = [
        Algorithm("cv_fallback", cv_fallback_factory, {"ok": True, "type": "opencv_connected_components"}),
    ]

    if not args.skip_sam:
        config = _sam_model_config()
        checkpoint = config["path"]
        checkpoint_ready = _is_sam_checkpoint_complete(checkpoint, config)
        if checkpoint_ready or args.try_sam_download:
            algorithms.append(
                Algorithm(
                    "legacy_sam",
                    lambda: sam_factory(args.device),
                    {
                        "ok": None,
                        "type": "segment_anything",
                        "checkpoint": checkpoint,
                        "checkpoint_ready_before_run": checkpoint_ready,
                        "download_enabled": bool(args.try_sam_download),
                    },
                )
            )
        else:
            algorithms.append(
                Algorithm(
                    "legacy_sam",
                    lambda: (_ for _ in ()).throw(RuntimeError("SAM checkpoint not available; rerun with --try-sam-download to download it")),
                    {
                        "ok": False,
                        "skipped": True,
                        "type": "segment_anything",
                        "checkpoint": checkpoint,
                        "reason": "checkpoint_not_available",
                    },
                )
            )

    if not args.skip_yolo:
        algorithms.append(
            Algorithm(
                "yolo11n_seg",
                lambda: yolo_seg_factory(args.yolo_weights, args.imgsz, args.yolo_conf),
                {"ok": None, "type": "ultralytics_yolo_seg", "weights": args.yolo_weights, "imgsz": args.imgsz, "conf": args.yolo_conf},
            )
        )

    if not args.skip_fastsam:
        algorithms.append(
            Algorithm(
                "fastsam_s",
                lambda: fastsam_factory(args.fastsam_weights, args.imgsz, args.fastsam_conf),
                {"ok": None, "type": "ultralytics_fastsam", "weights": args.fastsam_weights, "imgsz": args.imgsz, "conf": args.fastsam_conf},
            )
        )

    return algorithms


def write_summary(output_root: Path, manifest: dict[str, Any]) -> Path:
    lines = [
        "# DeckLens Layering Segmentation Research",
        "",
        f"- Created: {manifest['created_at']}",
        f"- Wall seconds: {manifest.get('wall_seconds', 0)}",
        f"- Inputs: {len(manifest['inputs'])}",
        f"- Output: `{manifest['output_dir']}`",
        "",
        "## Algorithm Results",
        "",
        "| Algorithm | Setup | Images OK | Avg Seconds | Avg Kept Masks | Avg Coverage | Initial Take |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    runs = manifest["runs"]
    by_algo: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_algo.setdefault(run["algorithm"], []).append(run)

    for name in sorted(by_algo):
        rows = by_algo[name]
        ok_rows = [row for row in rows if row["ok"]]
        setup = next((item for item in manifest["algorithm_setup"] if item["algorithm"] == name), {})
        setup_label = "ok" if setup.get("ok") is True else "skipped" if setup.get("skipped") else "failed" if setup.get("ok") is False else "attempted"
        avg_seconds = statistics.mean(row["seconds"] for row in ok_rows) if ok_rows else 0.0
        avg_masks = statistics.mean(row["summary"]["count"] for row in ok_rows) if ok_rows else 0.0
        avg_coverage = statistics.mean(row["summary"]["coverage_ratio"] for row in ok_rows) if ok_rows else 0.0
        take = make_initial_take(name, ok_rows, setup)
        lines.append(
            f"| {name} | {setup_label} | {len(ok_rows)}/{len(rows)} | {avg_seconds:.2f} | {avg_masks:.1f} | {avg_coverage:.3f} | {take} |"
        )

    lines.extend(["", "## Outputs", ""])
    for path in manifest.get("contact_sheets", []):
        lines.append(f"- `{path}`")
    lines.append("")
    path = output_root / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def make_initial_take(name: str, ok_rows: list[dict[str, Any]], setup: dict[str, Any]) -> str:
    if not ok_rows:
        if setup.get("skipped"):
            return "未跑通：缺本地模型或未启用下载。"
        return "未跑通：初始化或推理失败。"
    avg_count = statistics.mean(row["summary"]["count"] for row in ok_rows)
    avg_cov = statistics.mean(row["summary"]["coverage_ratio"] for row in ok_rows)
    if name == "yolo11n_seg":
        if avg_count < 1:
            return "不适合：COCO 实例分割基本不识别 PPT 图形元素。"
        return "偏弱：只识别少量真实物体类别，抽象 PPT 元素覆盖不足。"
    if name == "fastsam_s":
        if avg_count >= 3 and 0.03 <= avg_cov <= 0.75:
            return "可继续验证：候选多、速度可接受，但需人工合并/过滤。"
        return "可跑但不稳：mask 数量或覆盖率不理想。"
    if name == "legacy_sam":
        if avg_count >= 2:
            return "可用但重：质量需看图，成本和模型体积偏高。"
        return "跑通但召回不足。"
    if name == "cv_fallback":
        return "适合作兜底：快，但只能按颜色连通域切，复杂遮挡不够。"
    return "见可视化结果。"


def main() -> int:
    wall_started = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="test-materials/input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--device", default="mps", choices=["cpu", "mps"])
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--min-area-ratio", type=float, default=0.001)
    parser.add_argument("--max-area-ratio", type=float, default=0.80)
    parser.add_argument("--bg-color-threshold", type=float, default=30.0)
    parser.add_argument("--overlap-iou", type=float, default=0.70)
    parser.add_argument("--contact-thumb-width", type=int, default=760)
    parser.add_argument("--contact-cols", type=int, default=2)
    parser.add_argument("--max-images", type=int, default=0)
    parser.add_argument("--try-sam-download", action="store_true")
    parser.add_argument("--skip-sam", action="store_true")
    parser.add_argument("--skip-yolo", action="store_true")
    parser.add_argument("--skip-fastsam", action="store_true")
    parser.add_argument("--yolo-weights", default="test-materials/models/ultralytics/yolo11n-seg.pt")
    parser.add_argument("--yolo-conf", type=float, default=0.12)
    parser.add_argument("--fastsam-weights", default="test-materials/models/ultralytics/FastSAM-s.pt")
    parser.add_argument("--fastsam-conf", type=float, default=0.25)
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_dir).resolve() if args.output_dir else (Path("test-materials/output/layering-research").resolve() / timestamp)
    output_root.mkdir(parents=True, exist_ok=True)

    inputs = load_inputs(input_dir)
    if args.max_images > 0:
        inputs = inputs[: args.max_images]
    if not inputs:
        raise SystemExit(f"No input images found in {input_dir}")

    manifest: dict[str, Any] = {
        "created_at": timestamp,
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "inputs": [str(path) for path in inputs],
        "parameters": {
            "imgsz": args.imgsz,
            "min_area_ratio": args.min_area_ratio,
            "max_area_ratio": args.max_area_ratio,
            "bg_color_threshold": args.bg_color_threshold,
            "overlap_iou": args.overlap_iou,
        },
        "algorithm_setup": [],
        "runs": [],
        "contact_sheets": [],
    }

    algorithms = build_algorithms(args)
    runners: dict[str, Callable[[np.ndarray], list[dict[str, Any]]]] = {}
    for algorithm in algorithms:
        setup = {"algorithm": algorithm.name, **algorithm.setup}
        started = time.time()
        try:
            runners[algorithm.name] = algorithm.factory()
            setup["ok"] = setup.get("ok") if setup.get("ok") is False else True
        except Exception as exc:
            setup["ok"] = False
            setup["error"] = f"{type(exc).__name__}: {exc}"
        setup["setup_seconds"] = round(time.time() - started, 3)
        manifest["algorithm_setup"].append(setup)
        print(f"setup | {algorithm.name} | {'ok' if setup['ok'] else setup.get('error') or setup.get('reason')}", flush=True)

    for image_path in inputs:
        image_rgb = np.array(Image.open(image_path).convert("RGB"))
        img_h, img_w = image_rgb.shape[:2]
        total_area = img_h * img_w
        overlays = []

        for algorithm in algorithms:
            row: dict[str, Any] = {
                "image": str(image_path),
                "algorithm": algorithm.name,
                "ok": False,
                "seconds": 0.0,
                "raw_count": 0,
                "postprocess": None,
                "summary": None,
                "overlay": None,
                "masks_npz": None,
                "error": None,
            }
            started = time.time()
            try:
                if algorithm.name not in runners:
                    setup = next((item for item in manifest["algorithm_setup"] if item["algorithm"] == algorithm.name), {})
                    raise RuntimeError(setup.get("error") or setup.get("reason") or "algorithm setup failed")
                raw_masks = runners[algorithm.name](image_rgb)
                masks, pp_stats = post_process_masks(
                    image_rgb,
                    raw_masks,
                    args.min_area_ratio,
                    args.max_area_ratio,
                    args.bg_color_threshold,
                    args.overlap_iou,
                )
                overlay_path = output_root / "overlays" / algorithm.name / f"{image_path.stem}.jpg"
                masks_path = output_root / "masks" / algorithm.name / f"{image_path.stem}.npz"
                title = f"{algorithm.name}: raw={len(raw_masks)}, kept={len(masks)}"
                save_overlay(overlay_path, image_rgb, masks, title)
                save_masks_npz(masks_path, masks)
                row.update(
                    {
                        "ok": True,
                        "raw_count": len(raw_masks),
                        "postprocess": pp_stats,
                        "summary": summarize_masks(masks, total_area),
                        "overlay": str(overlay_path),
                        "masks_npz": str(masks_path),
                    }
                )
                overlays.append((algorithm.name, overlay_path))
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.time() - started, 3)
            manifest["runs"].append(row)
            status = "ok" if row["ok"] else row["error"]
            kept = row["summary"]["count"] if row["summary"] else 0
            print(f"{image_path.name} | {algorithm.name} | {status} | kept={kept} | {row['seconds']}s", flush=True)

        sheet_path = create_contact_sheet(image_path, output_root, overlays, args.contact_thumb_width, args.contact_cols)
        manifest["contact_sheets"].append(str(sheet_path))
        print(f"contact_sheet | {sheet_path}", flush=True)

    manifest["finished_at"] = time.strftime("%Y%m%d-%H%M%S")
    manifest["wall_seconds"] = round(time.time() - wall_started, 3)

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path = write_summary(output_root, manifest)
    print(f"manifest | {manifest_path}", flush=True)
    print(f"summary | {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
