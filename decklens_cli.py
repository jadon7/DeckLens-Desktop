#!/usr/bin/env python3
"""Command line entry point for DeckLens conversions."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

SUPPORTED_INPUTS = {".png", ".jpg", ".jpeg", ".pdf"}
INPAINT_BACKENDS = {"lama", "local_mean"}


def default_inpaint_backend() -> str:
    if os.name == "nt" and os.environ.get("DECKLENS_DISABLE_TORCH", "1").strip().lower() in {"1", "true", "yes", "on"}:
        return "local_mean"
    return os.environ.get("DECKLENS_INPAINT_BACKEND", "lama")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="decklens",
        description="Convert image-like presentation pages into an editable PPTX deck.",
    )
    parser.add_argument("inputs", nargs="+", help="Input image or PDF files.")
    parser.add_argument("-o", "--output", help="Output .pptx path.")
    parser.add_argument("--output-dir", help="Directory for the output PPTX when --output is omitted.")
    parser.add_argument(
        "--mode",
        choices=["standard", "element", "ai"],
        default="standard",
        help="Conversion mode. 'element' auto-generates layers without the interactive preview.",
    )
    parser.add_argument(
        "--inpaint-backend",
        choices=sorted(INPAINT_BACKENDS),
        default=default_inpaint_backend(),
        help="Background cleanup algorithm.",
    )
    parser.add_argument("--device", default=os.environ.get("DECKLENS_DEVICE", "cpu"), help="Processing device.")
    parser.add_argument("--qwen-layers", type=int, default=4, help="AI layered restore count, 3-8.")
    parser.add_argument("--fal-key", default=os.environ.get("FAL_KEY", ""), help="fal.ai API key for --mode ai.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing output PPTX.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable conversion metadata.")
    return parser.parse_args()


def validate_inputs(inputs: list[str]) -> list[Path]:
    paths = []
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input not found: {path}")
        if path.suffix.lower() not in SUPPORTED_INPUTS:
            raise ValueError(f"Unsupported input type: {path.suffix} ({path})")
        paths.append(path)
    return paths


def default_output_path(inputs: list[Path], output_dir: str | None) -> Path:
    directory = Path(output_dir).expanduser().resolve() if output_dir else inputs[0].parent
    directory.mkdir(parents=True, exist_ok=True)
    stem = inputs[0].stem if len(inputs) == 1 else f"{inputs[0].stem}_decklens"
    return directory / f"{stem}.pptx"


def expand_inputs(inputs: list[Path], temp_dir: str) -> list[str]:
    from engine import pdf_to_images

    image_paths: list[str] = []
    for path in inputs:
        if path.suffix.lower() == ".pdf":
            pages = pdf_to_images(str(path), dpi=300, output_dir=temp_dir)
            image_paths.extend(pages)
        else:
            image_paths.append(str(path))
    return image_paths


def main() -> int:
    args = parse_args()
    try:
        from engine import images_to_pptx

        if args.inpaint_backend not in INPAINT_BACKENDS:
            raise ValueError(f"Unsupported inpaint backend: {args.inpaint_backend}")
        if os.name == "nt" and os.environ.get("DECKLENS_DISABLE_TORCH", "1").strip().lower() in {"1", "true", "yes", "on"} and args.inpaint_backend == "lama":
            args.inpaint_backend = "local_mean"

        inputs = validate_inputs(args.inputs)
        output = Path(args.output).expanduser().resolve() if args.output else default_output_path(inputs, args.output_dir)
        if output.exists() and not args.overwrite:
            raise FileExistsError(f"Output already exists, pass --overwrite to replace it: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)

        mode = args.mode
        if mode == "ai" and not args.fal_key:
            raise ValueError("AI mode requires --fal-key or FAL_KEY.")
        decompose = mode != "standard"
        decompose_mode = "qwen" if mode == "ai" else "sam" if mode == "element" else "none"
        qwen_layers = max(3, min(8, args.qwen_layers))

        with tempfile.TemporaryDirectory(prefix="decklens_cli_") as temp_dir:
            image_paths = expand_inputs(inputs, temp_dir)

            def progress(current: int, total: int, filename: str, message: str) -> None:
                if not args.json:
                    print(f"[{current + 1}/{total}] {filename}: {message}", flush=True)

            images_to_pptx(
                image_paths=image_paths,
                output_path=str(output),
                device=args.device,
                progress_callback=progress,
                decompose=decompose,
                decompose_mode=decompose_mode,
                qwen_num_layers=qwen_layers,
                qwen_api_key=args.fal_key,
                inpaint_backend=args.inpaint_backend,
            )

        result = {
            "ok": True,
            "output": str(output),
            "slides": len(image_paths),
            "mode": mode,
            "inpaint_backend": args.inpaint_backend,
        }
        print(json.dumps(result, ensure_ascii=False) if args.json else f"Output: {output}")
        return 0
    except Exception as error:
        if args.json:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"DeckLens CLI failed: {error}", file=sys.stderr)
        return 1
    finally:
        if "engine" in sys.modules:
            from engine import release_cached_models

            release_cached_models()


if __name__ == "__main__":
    raise SystemExit(main())
