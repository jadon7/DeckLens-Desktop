#!/usr/bin/env python3
"""
Run semantic candidate-box experiments for DeckLens layering research.

This is intentionally outside the product path. It probes whether open-vocabulary
detectors and UI parsers are useful for decomposing slide screenshots into
editable visual layers.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import platform
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_LABELS = [
    "title text",
    "body text",
    "small text",
    "button",
    "icon",
    "logo",
    "chart",
    "graph",
    "table",
    "photo",
    "illustration",
    "card",
    "panel",
    "shape",
    "line",
]


@dataclass
class Detection:
    label: str
    box: list[float]
    score: float | None = None
    content: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {"label": self.label, "box": [round(v, 2) for v in self.box]}
        if self.score is not None:
            data["score"] = round(float(self.score), 4)
        if self.content:
            data["content"] = self.content
        return data


def load_inputs(input_dir: Path, limit: int | None) -> list[Path]:
    inputs = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    return inputs[:limit] if limit else inputs


def select_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def exception_payload(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


def import_state(names: Iterable[str]) -> dict[str, str]:
    state = {}
    for name in names:
        state[name] = "ok" if importlib.util.find_spec(name) else "missing"
    return state


def clamp_box(box: Iterable[float], width: int, height: int) -> list[float]:
    x0, y0, x1, y1 = [float(v) for v in box]
    x0 = max(0.0, min(float(width), x0))
    x1 = max(0.0, min(float(width), x1))
    y0 = max(0.0, min(float(height), y0))
    y1 = max(0.0, min(float(height), y1))
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return [x0, y0, x1, y1]


def box_area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_iou(left: list[float], right: list[float]) -> float:
    ix0 = max(left[0], right[0])
    iy0 = max(left[1], right[1])
    ix1 = min(left[2], right[2])
    iy1 = min(left[3], right[3])
    intersection = box_area([ix0, iy0, ix1, iy1])
    if intersection <= 0:
        return 0.0
    union = box_area(left) + box_area(right) - intersection
    return intersection / union if union > 0 else 0.0


def nms_detections(detections: list[Detection], iou_threshold: float) -> list[Detection]:
    if iou_threshold <= 0:
        return detections
    pending = sorted(detections, key=lambda det: det.score if det.score is not None else 0.0, reverse=True)
    keep: list[Detection] = []
    for det in pending:
        if all(box_iou(det.box, kept.box) < iou_threshold for kept in keep):
            keep.append(det)
    return keep


def normalize_detections(
    detections: list[Detection],
    width: int,
    height: int,
    min_area_px: int,
    max_area_ratio: float,
    nms_iou: float,
) -> list[Detection]:
    normalized = []
    max_area = width * height * max_area_ratio
    for det in detections:
        box = clamp_box(det.box, width, height)
        area = box_area(box)
        if area < min_area_px or area > max_area:
            continue
        normalized.append(Detection(label=det.label, score=det.score, box=box, content=det.content))
    return nms_detections(normalized, nms_iou)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_detections(image: Image.Image, detections: list[Detection], title: str) -> Image.Image:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = load_font(max(14, round(image.width / 100)))
    palette = [
        (232, 76, 61, 210),
        (46, 134, 222, 210),
        (39, 174, 96, 210),
        (155, 89, 182, 210),
        (230, 126, 34, 210),
        (22, 160, 133, 210),
    ]
    for idx, det in enumerate(detections):
        color = palette[idx % len(palette)]
        x0, y0, x1, y1 = det.box
        draw.rectangle((x0, y0, x1, y1), outline=color, width=max(2, image.width // 500))
        label = det.label
        if det.score is not None:
            label = f"{label} {det.score:.2f}"
        text_box = draw.textbbox((x0, y0), label, font=font)
        tw = text_box[2] - text_box[0]
        th = text_box[3] - text_box[1]
        label_y = max(0, y0 - th - 6)
        draw.rectangle((x0, label_y, min(image.width, x0 + tw + 8), label_y + th + 6), fill=(255, 255, 255, 230))
        draw.text((x0 + 4, label_y + 3), label, fill=(15, 15, 15, 255), font=font)

    title_font = load_font(max(18, round(image.width / 78)))
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.rectangle((0, 0, min(image.width, title_box[2] + 18), title_box[3] + 14), fill=(255, 255, 255, 235))
    draw.text((9, 7), title, fill=(10, 10, 10, 255), font=title_font)
    return canvas


def make_contact_sheets(output_root: Path, image_paths: list[Path], algorithm_ids: list[str], thumb_width: int, cols: int) -> list[str]:
    out_dir = output_root / "contact-sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    font = load_font(max(16, thumb_width // 42))
    paths = []
    for image_path in image_paths:
        original = Image.open(image_path).convert("RGB")
        thumb_h = round(original.height * thumb_width / original.width)
        gap = max(10, thumb_width // 80)
        header_h = max(34, thumb_width // 24)
        cells: list[tuple[str, Image.Image]] = [("original", original)]
        for algorithm_id in algorithm_ids:
            vis = output_root / "visualizations" / algorithm_id / f"{image_path.stem}.jpg"
            if vis.exists():
                cells.append((algorithm_id, Image.open(vis).convert("RGB")))
        rows = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb_width + (cols + 1) * gap, rows * (thumb_h + header_h) + (rows + 1) * gap), "white")
        draw = ImageDraw.Draw(sheet)
        for idx, (label, cell) in enumerate(cells):
            x = gap + (idx % cols) * (thumb_width + gap)
            y = gap + (idx // cols) * (thumb_h + header_h + gap)
            draw.text((x, y), label, fill=(20, 20, 20), font=font)
            sheet.paste(cell.resize((thumb_width, thumb_h), Image.Resampling.LANCZOS), (x, y + header_h))
        out_path = out_dir / f"{image_path.stem}__semantic_candidates.jpg"
        sheet.save(out_path, quality=92)
        paths.append(str(out_path))
    return paths


class GroundingDinoAdapter:
    algorithm_id = "groundingdino_tiny_zero_shot"
    model_id = "IDEA-Research/grounding-dino-tiny"

    def __init__(self, labels: list[str], device: str, box_threshold: float, text_threshold: float):
        self.labels = labels
        self.device = device
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.detector = None

    def setup(self) -> dict[str, Any]:
        from transformers import pipeline

        self.detector = pipeline("zero-shot-object-detection", model=self.model_id, device=self.device)
        return {
            "algorithm": self.algorithm_id,
            "model": self.model_id,
            "device": self.device,
            "ok": True,
            "api": "transformers.pipeline('zero-shot-object-detection')",
            "box_threshold": self.box_threshold,
            "text_threshold": self.text_threshold,
            "note": "Pipeline API preserves candidate_labels in output. text_threshold is recorded for comparability but the pipeline exposes one threshold.",
        }

    def run(self, image: Image.Image) -> list[Detection]:
        assert self.detector is not None
        predictions = self.detector(image, candidate_labels=self.labels, threshold=self.box_threshold)
        detections = []
        for item in predictions:
            box = item["box"]
            detections.append(
                Detection(
                    label=str(item.get("label", "")),
                    score=float(item["score"]),
                    box=[float(box["xmin"]), float(box["ymin"]), float(box["xmax"]), float(box["ymax"])],
                )
            )
        return detections


class Florence2ODAdapter:
    algorithm_id = "florence2_base_od"
    model_id = "microsoft/Florence-2-base"

    def __init__(self, device: str):
        self.device = device
        self.processor = None
        self.model = None
        self.torch_dtype = None

    def setup(self) -> dict[str, Any]:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        self.torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=self.torch_dtype,
            trust_remote_code=True,
            attn_implementation="eager",
        ).to(self.device)
        self.model.eval()
        return {
            "algorithm": self.algorithm_id,
            "model": self.model_id,
            "device": self.device,
            "ok": True,
            "torch_dtype": str(self.torch_dtype),
            "attn_implementation": "eager",
            "task_prompt": "<OD>",
        }

    def run(self, image: Image.Image) -> list[Detection]:
        import torch

        assert self.processor is not None and self.model is not None and self.torch_dtype is not None
        prompt = "<OD>"
        inputs = self.processor(text=prompt, images=image, return_tensors="pt").to(self.device, self.torch_dtype)
        with torch.inference_mode():
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                do_sample=False,
                num_beams=3,
                use_cache=False,
            )
        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed = self.processor.post_process_generation(generated_text, task=prompt, image_size=image.size)
        payload = parsed.get(prompt, parsed)
        boxes = payload.get("bboxes") or payload.get("boxes") or []
        labels = payload.get("labels") or ["object"] * len(boxes)
        return [Detection(label=str(label), box=[float(v) for v in box]) for box, label in zip(boxes, labels)]


class OmniParserAdapter:
    algorithm_id = "omniparser_v2_endpoint"
    model_id = "microsoft/OmniParser-v2.0"

    def __init__(self):
        self.handler = None
        self.snapshot_path: Path | None = None

    def setup(self) -> dict[str, Any]:
        from huggingface_hub import hf_hub_download, snapshot_download

        handler_path = hf_hub_download(self.model_id, "handler.py", repo_type="model")
        spec = importlib.util.spec_from_file_location("omniparser_v2_handler", handler_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not import OmniParser handler from {handler_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.snapshot_path = Path(snapshot_download(self.model_id, repo_type="model"))
        self.handler = module.EndpointHandler(str(self.snapshot_path))
        return {
            "algorithm": self.algorithm_id,
            "model": self.model_id,
            "ok": True,
            "snapshot": str(self.snapshot_path),
            "note": "OmniParser uses its endpoint handler: YOLO icon detector, Florence-2 icon captioner, and OCR dependencies.",
        }

    def run(self, image: Image.Image) -> list[Detection]:
        assert self.handler is not None
        rgb = image.convert("RGB")
        buffer = sys.modules["io"].BytesIO() if "io" in sys.modules else None
        if buffer is None:
            import io

            buffer = io.BytesIO()
        rgb.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        result = self.handler({"inputs": {"image": encoded}})
        detections = []
        for item in result.get("bboxes", []):
            box = item.get("bbox") or item.get("box")
            if not box:
                continue
            if max(box) <= 1.5:
                w, h = image.size
                box = [box[0] * w, box[1] * h, box[2] * w, box[3] * h]
            label = str(item.get("type") or item.get("label") or "ui")
            content = item.get("content")
            detections.append(Detection(label=label, box=[float(v) for v in box], content=str(content) if content else None))
        return detections


def build_adapters(selected: list[str], labels: list[str], device: str, args: argparse.Namespace) -> list[Any]:
    adapters = []
    if "groundingdino" in selected:
        adapters.append(GroundingDinoAdapter(labels, device, args.grounding_box_threshold, args.grounding_text_threshold))
    if "florence2" in selected:
        adapters.append(Florence2ODAdapter(device))
    if "omniparser" in selected:
        adapters.append(OmniParserAdapter())
    return adapters


def run_algorithm(
    adapter: Any,
    inputs: list[Path],
    output_root: Path,
    min_area_px: int,
    max_area_ratio: float,
    nms_iou: float,
) -> list[dict[str, Any]]:
    rows = []
    for image_path in inputs:
        started = time.time()
        row = {
            "algorithm": adapter.algorithm_id,
            "image": str(image_path),
            "ok": False,
            "seconds": None,
            "count": 0,
            "detections": None,
            "visualization": None,
            "error": None,
        }
        try:
            image = Image.open(image_path).convert("RGB")
            detections = normalize_detections(adapter.run(image), image.width, image.height, min_area_px, max_area_ratio, nms_iou)
            detection_path = output_root / "detections" / adapter.algorithm_id / f"{image_path.stem}.json"
            visualization_path = output_root / "visualizations" / adapter.algorithm_id / f"{image_path.stem}.jpg"
            visualization_path.parent.mkdir(parents=True, exist_ok=True)
            save_json(
                detection_path,
                {
                    "image": str(image_path),
                    "size": [image.width, image.height],
                    "algorithm": adapter.algorithm_id,
                    "detections": [det.as_dict() for det in detections],
                },
            )
            draw_detections(image, detections, f"{adapter.algorithm_id}: {len(detections)} boxes").save(visualization_path, quality=92)
            row.update(
                {
                    "ok": True,
                    "count": len(detections),
                    "detections": str(detection_path),
                    "visualization": str(visualization_path),
                }
            )
        except Exception as exc:
            row["error"] = exception_payload(exc)
        row["seconds"] = round(time.time() - started, 3)
        rows.append(row)
        status = "ok" if row["ok"] else f"failed: {row['error']['type']}: {row['error']['message']}"
        print(f"{adapter.algorithm_id} | {image_path.name} | {status} | {row['seconds']}s", flush=True)
    return rows


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for run in runs:
        item = summary.setdefault(run["algorithm"], {"ok_images": 0, "failed_images": 0, "total_seconds": 0.0, "counts": []})
        item["total_seconds"] += float(run["seconds"] or 0)
        if run["ok"]:
            item["ok_images"] += 1
            item["counts"].append(run["count"])
        else:
            item["failed_images"] += 1
    for item in summary.values():
        counts = item.pop("counts")
        item["total_seconds"] = round(item["total_seconds"], 3)
        item["avg_boxes"] = round(sum(counts) / len(counts), 2) if counts else 0
        item["min_boxes"] = min(counts) if counts else 0
        item["max_boxes"] = max(counts) if counts else 0
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="test-materials/input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--algorithms", default="groundingdino,florence2,omniparser")
    parser.add_argument("--labels", default=",".join(DEFAULT_LABELS))
    parser.add_argument("--grounding-box-threshold", type=float, default=0.18)
    parser.add_argument("--grounding-text-threshold", type=float, default=0.16)
    parser.add_argument("--min-area-px", type=int, default=120)
    parser.add_argument("--max-area-ratio", type=float, default=0.85)
    parser.add_argument("--nms-iou", type=float, default=0.82)
    parser.add_argument("--contact-thumb-width", type=int, default=860)
    parser.add_argument("--contact-cols", type=int, default=2)
    args = parser.parse_args()

    started = time.time()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    input_dir = Path(args.input_dir).resolve()
    output_root = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (Path("test-materials/output/layering-semantic-research").resolve() / timestamp)
    )
    output_root.mkdir(parents=True, exist_ok=True)

    selected = [item.strip().lower() for item in args.algorithms.split(",") if item.strip()]
    labels = [item.strip() for item in args.labels.split(",") if item.strip()]
    device = select_device(args.device)
    inputs = load_inputs(input_dir, args.limit)
    if not inputs:
        raise SystemExit(f"No input images found in {input_dir}")

    manifest: dict[str, Any] = {
        "created_at": timestamp,
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "device": device,
        "selected_algorithms": selected,
        "candidate_labels": labels,
        "filters": {
            "min_area_px": args.min_area_px,
            "max_area_ratio": args.max_area_ratio,
            "nms_iou": args.nms_iou,
        },
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "imports": import_state(
                [
                    "transformers",
                    "torch",
                    "cv2",
                    "huggingface_hub",
                    "easyocr",
                    "ultralytics",
                    "supervision",
                    "einops",
                    "timm",
                ]
            ),
        },
        "inputs": [str(path) for path in inputs],
        "algorithm_setup": [],
        "runs": [],
    }
    save_json(output_root / "manifest.json", manifest)

    adapters = build_adapters(selected, labels, device, args)
    runnable = []
    for adapter in adapters:
        setup_started = time.time()
        try:
            setup = adapter.setup()
            setup["seconds"] = round(time.time() - setup_started, 3)
            manifest["algorithm_setup"].append(setup)
            runnable.append(adapter)
            print(f"{adapter.algorithm_id} setup ok | {setup['seconds']}s", flush=True)
        except Exception as exc:
            payload = {
                "algorithm": adapter.algorithm_id,
                "model": getattr(adapter, "model_id", None),
                "ok": False,
                "seconds": round(time.time() - setup_started, 3),
                "error": exception_payload(exc),
            }
            manifest["algorithm_setup"].append(payload)
            print(f"{adapter.algorithm_id} setup failed: {payload['error']['type']}: {payload['error']['message']}", flush=True)
        save_json(output_root / "manifest.json", manifest)

    for adapter in runnable:
        manifest["runs"].extend(run_algorithm(adapter, inputs, output_root, args.min_area_px, args.max_area_ratio, args.nms_iou))
        save_json(output_root / "manifest.json", manifest)

    successful_algorithms = [item["algorithm"] for item in manifest["algorithm_setup"] if item.get("ok")]
    manifest["contact_sheets"] = make_contact_sheets(output_root, inputs, successful_algorithms, args.contact_thumb_width, args.contact_cols)
    manifest["summary"] = summarize_runs(manifest["runs"])
    manifest["total_seconds"] = round(time.time() - started, 3)
    save_json(output_root / "manifest.json", manifest)
    save_json(output_root / "summary.json", manifest["summary"])

    print(f"Manifest: {output_root / 'manifest.json'}", flush=True)
    print(f"Total: {manifest['total_seconds']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
