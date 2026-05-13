#!/usr/bin/env python3
"""
Run local background-cleanup experiments for DeckLens test materials.

This script is intentionally outside the product path. It compares the current
OpenCV inpainting variants, the existing PyTorch LaMa path, and the OpenCV Zoo
LaMa ONNX model when the local OpenCV build can load it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import TextBlock, detect_text_paddle, get_lama_model


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
ONNX_MODEL_URL = "https://huggingface.co/opencv/inpainting_lama/resolve/main/inpainting_lama_2025jan.onnx"


def load_inputs(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS and p.is_file())


def block_to_dict(block: TextBlock) -> dict:
    data = asdict(block)
    data["color"] = list(block.color)
    return data


def dict_to_block(data: dict) -> TextBlock:
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
        json.dumps({"image": str(image_path), "blocks": [block_to_dict(b) for b in blocks]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return blocks


def make_box_mask(shape: tuple[int, int], blocks: list[TextBlock], dilate_px: int = 0) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    for block in blocks:
        x0 = max(0, block.x)
        y0 = max(0, block.y)
        x1 = min(w, block.x + block.w)
        y1 = min(h, block.y + block.h)
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 255
    if dilate_px > 0 and np.any(mask):
        kernel_size = dilate_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def make_feather_alpha(mask: np.ndarray, blur_px: int) -> np.ndarray:
    if blur_px <= 0 or not np.any(mask):
        return (mask.astype(np.float32) / 255.0)[..., None]
    k = blur_px * 2 + 1
    if k % 2 == 0:
        k += 1
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (k, k), 0)
    alpha = np.clip(alpha, 0.0, 1.0)
    return alpha[..., None]


def blend_with_alpha(original_bgr: np.ndarray, inpainted_bgr: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    blended = inpainted_bgr.astype(np.float32) * alpha + original_bgr.astype(np.float32) * (1.0 - alpha)
    return np.clip(blended, 0, 255).astype(np.uint8)


def inpaint_opencv(flag: int, radius: int) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    def run(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return cv2.inpaint(image_bgr, mask, radius, flag)

    return run


def inpaint_torch_lama(max_side: int = 1024, device: str = "cpu") -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    model = get_lama_model(device)

    def run(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        import torch

        h, w = image_bgr.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        work_bgr = image_bgr
        work_mask = mask
        if scale < 1.0:
            work_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
            work_bgr = cv2.resize(image_bgr, work_size, interpolation=cv2.INTER_AREA)
            work_mask = cv2.resize(mask, work_size, interpolation=cv2.INTER_NEAREST)

        rgb = cv2.cvtColor(work_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mask_float = (work_mask > 0).astype(np.float32)
        image_tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
        mask_tensor = torch.from_numpy(mask_float).unsqueeze(0).unsqueeze(0)

        model_device = next(model.parameters()).device
        image_tensor = image_tensor.to(model_device)
        mask_tensor = mask_tensor.to(model_device)
        with torch.no_grad():
            output = model(image_tensor, mask_tensor)
        output = output[0].detach().cpu().permute(1, 2, 0).numpy()
        output = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        out_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
        if out_bgr.shape[:2] != (h, w):
            out_bgr = cv2.resize(out_bgr, (w, h), interpolation=cv2.INTER_CUBIC)
        return out_bgr

    return run


class OpenCVLamaONNX:
    def __init__(self, model_path: Path):
        self.net = cv2.dnn.readNetFromONNX(str(model_path))

    def __call__(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        h, w = image_bgr.shape[:2]
        image_blob = cv2.dnn.blobFromImage(image_bgr, 0.00392, (512, 512), (0, 0, 0), False, False)
        mask_blob = cv2.dnn.blobFromImage(mask, scalefactor=1.0, size=(512, 512), mean=(0,), swapRB=False, crop=False)
        mask_blob = (mask_blob > 0).astype(np.float32)
        self.net.setInput(image_blob, "image")
        self.net.setInput(mask_blob, "mask")
        output = self.net.forward()[0]
        output = np.transpose(output, (1, 2, 0)).astype(np.uint8)
        return cv2.resize(output, (w, h), interpolation=cv2.INTER_CUBIC)


class ORTLamaONNX:
    def __init__(self, model_path: Path):
        import onnxruntime as ort

        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), providers=providers)

    def __call__(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        h, w = image_bgr.shape[:2]
        image_blob = cv2.dnn.blobFromImage(image_bgr, 0.00392, (512, 512), (0, 0, 0), False, False).astype(np.float32)
        mask_blob = cv2.dnn.blobFromImage(mask, scalefactor=1.0, size=(512, 512), mean=(0,), swapRB=False, crop=False)
        mask_blob = (mask_blob > 0).astype(np.float32)
        output = self.session.run(None, {"image": image_blob, "mask": mask_blob})[0][0]
        output = np.transpose(output, (1, 2, 0))
        if output.max() <= 1.5:
            output = output * 255.0
        output = np.clip(output, 0, 255).astype(np.uint8)
        return cv2.resize(output, (w, h), interpolation=cv2.INTER_CUBIC)


def ensure_onnx_model(path: Path) -> Path:
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(ONNX_MODEL_URL, path)
    return path


def save_png(path: Path, image_bgr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image_bgr)


def run_case(
    image_path: Path,
    blocks: list[TextBlock],
    output_root: Path,
    algorithms: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]],
    feather_dilate_px: int,
    feather_blur_px: int,
) -> list[dict]:
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise ValueError(f"Cannot read image: {image_path}")
    h, w = image_bgr.shape[:2]

    hard_mask = make_box_mask((h, w), blocks, dilate_px=0)
    expanded_mask = make_box_mask((h, w), blocks, dilate_px=feather_dilate_px)
    feather_alpha = make_feather_alpha(expanded_mask, blur_px=feather_blur_px)

    mask_dir = output_root / "masks"
    save_png(mask_dir / f"{image_path.stem}__hard.png", hard_mask)
    save_png(mask_dir / f"{image_path.stem}__feather_expanded.png", expanded_mask)
    cv2.imwrite(str(mask_dir / f"{image_path.stem}__feather_alpha.png"), np.clip(feather_alpha[..., 0] * 255, 0, 255).astype(np.uint8))

    rows = []
    for name, algorithm in algorithms.items():
        for mask_name, mask, alpha in (
            ("hard", hard_mask, None),
            ("feather", expanded_mask, feather_alpha),
        ):
            started = time.time()
            row = {
                "image": str(image_path),
                "algorithm": name,
                "mask": mask_name,
                "text_blocks": len(blocks),
                "ok": False,
                "seconds": None,
                "output": None,
                "error": None,
            }
            try:
                result = algorithm(image_bgr, mask)
                if alpha is not None:
                    result = blend_with_alpha(image_bgr, result, alpha)
                out_path = output_root / name / mask_name / f"{image_path.stem}.png"
                save_png(out_path, result)
                row["ok"] = True
                row["output"] = str(out_path)
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.time() - started, 3)
            rows.append(row)
            print(f"{image_path.name} | {name} | {mask_name} | {'ok' if row['ok'] else row['error']} | {row['seconds']}s", flush=True)
    return rows


def create_contact_sheets(output_root: Path, manifest: dict, sheet_thumb_width: int, sheet_cols: int) -> list[str]:
    algorithms = sorted({run["algorithm"] for run in manifest["runs"] if run["ok"]})
    inputs = sorted({Path(run["image"]) for run in manifest["runs"]})
    summary_dir = output_root / "contact-sheets"
    summary_dir.mkdir(parents=True, exist_ok=True)

    try:
        label_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", max(18, sheet_thumb_width // 36))
    except Exception:
        label_font = None

    output_paths = []
    for input_path in inputs:
        original = Image.open(input_path).convert("RGB")
        thumb_w = sheet_thumb_width
        thumb_h = round(original.height * thumb_w / original.width)
        header_h = max(42, thumb_w // 18)
        gap = max(12, thumb_w // 70)
        labels: list[tuple[str, Image.Image]] = [("original", original)]

        for algorithm in algorithms:
            for mask_name in ("hard", "feather"):
                path = output_root / algorithm / mask_name / f"{input_path.stem}.png"
                if path.exists():
                    labels.append((f"{algorithm} / {mask_name}", Image.open(path).convert("RGB")))

        cols = max(1, sheet_cols)
        rows = (len(labels) + cols - 1) // cols
        sheet = Image.new(
            "RGB",
            (cols * thumb_w + (cols + 1) * gap, rows * (thumb_h + header_h) + (rows + 1) * gap),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for index, (label, image) in enumerate(labels):
            x = gap + (index % cols) * (thumb_w + gap)
            y = gap + (index // cols) * (thumb_h + header_h + gap)
            draw.text((x, y), label, fill=(20, 20, 20), font=label_font)
            thumb = image.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (x, y + header_h))

        out_path = summary_dir / f"{input_path.stem}__comparison.jpg"
        sheet.save(out_path, quality=94)
        output_paths.append(str(out_path))
        print(f"Contact sheet: {out_path}", flush=True)

    return output_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="test-materials/input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument("--feather-dilate", type=int, default=12)
    parser.add_argument("--feather-blur", type=int, default=21)
    parser.add_argument("--contact-thumb-width", type=int, default=900)
    parser.add_argument("--contact-cols", type=int, default=2)
    parser.add_argument("--skip-torch-lama", action="store_true")
    parser.add_argument("--skip-opencv-lama-onnx", action="store_true")
    parser.add_argument("--skip-ort-lama-onnx", action="store_true")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_dir).resolve() if args.output_dir else Path("test-materials/output/inpaint-research").resolve() / timestamp
    ocr_cache = output_root / "ocr"
    inputs = load_inputs(input_dir)
    if not inputs:
        raise SystemExit(f"No input images found in {input_dir}")

    algorithms: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
        "opencv_telea_r3": inpaint_opencv(cv2.INPAINT_TELEA, 3),
        "opencv_telea_r7": inpaint_opencv(cv2.INPAINT_TELEA, 7),
        "opencv_ns_r5": inpaint_opencv(cv2.INPAINT_NS, 5),
    }

    algorithm_setup = []
    if not args.skip_torch_lama:
        try:
            algorithms["torch_lama_1024"] = inpaint_torch_lama(max_side=1024, device=args.device)
            algorithm_setup.append({"algorithm": "torch_lama_1024", "ok": True})
        except Exception as exc:
            algorithm_setup.append({"algorithm": "torch_lama_1024", "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    if not args.skip_opencv_lama_onnx:
        try:
            model_path = ensure_onnx_model(Path("test-materials/models/opencv/inpainting_lama_2025jan.onnx").resolve())
            algorithms["opencv_lama_onnx_512"] = OpenCVLamaONNX(model_path)
            algorithm_setup.append({"algorithm": "opencv_lama_onnx_512", "ok": True, "model": str(model_path), "size_bytes": model_path.stat().st_size})
        except Exception as exc:
            algorithm_setup.append({"algorithm": "opencv_lama_onnx_512", "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    if not args.skip_ort_lama_onnx:
        try:
            model_path = ensure_onnx_model(Path("test-materials/models/opencv/inpainting_lama_2025jan.onnx").resolve())
            algorithms["ort_lama_onnx_512"] = ORTLamaONNX(model_path)
            algorithm_setup.append({"algorithm": "ort_lama_onnx_512", "ok": True, "model": str(model_path), "size_bytes": model_path.stat().st_size})
        except Exception as exc:
            algorithm_setup.append({"algorithm": "ort_lama_onnx_512", "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": timestamp,
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "mask_variants": {
            "hard": "OCR bounding boxes as binary mask.",
            "feather": f"Mask dilated by {args.feather_dilate}px for inference, then Gaussian-blurred alpha blend over the original image with blur radius {args.feather_blur}px.",
        },
        "algorithm_setup": algorithm_setup,
        "contact_sheet": {
            "thumb_width": args.contact_thumb_width,
            "cols": args.contact_cols,
        },
        "runs": [],
    }

    for image_path in inputs:
        blocks = get_or_detect_blocks(image_path, ocr_cache, force_ocr=args.force_ocr)
        manifest["runs"].extend(run_case(image_path, blocks, output_root, algorithms, args.feather_dilate, args.feather_blur))

    manifest["contact_sheets"] = create_contact_sheets(output_root, manifest, args.contact_thumb_width, args.contact_cols)

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
