#!/usr/bin/env python3
"""
Run local raster-to-vector methods against screened DeckLens layer candidates.

Research script only. It does not integrate with the app.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


METHODS = ("vtracer", "vtracer_clean", "vtracer_poster", "imagetracerjs", "potrace_mask", "autotrace")


@dataclass
class MethodResult:
    method: str
    ok: bool
    svg: str | None
    render: str | None
    bytes: int | None
    error: str | None


@dataclass
class VectorizedCandidate:
    id: str
    tier: str
    source_cutout: str
    source_image: str
    mask_key: str
    methods: list[MethodResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates-json",
        type=Path,
        default=Path("test-materials/output/vectorization-candidates/20260513-fastsam-screening-v6/candidates.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test-materials/output/vectorization-eval") / datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--limit", type=int, default=0, help="0 means all strong/review candidates.")
    return parser


def selected_candidates(candidates_json: Path, limit: int) -> list[dict]:
    data = json.loads(candidates_json.read_text(encoding="utf-8"))
    selected = [s for s in data["scores"] if s["candidate_tier"] in {"strong", "review"}]
    selected.sort(key=lambda s: (s["candidate_tier"] != "strong", -s["vector_score"]))
    if limit > 0:
        selected = selected[:limit]
    return selected


def render_svg(svg_path: Path, out_path: Path) -> tuple[bool, str | None]:
    if not shutil.which("magick"):
        return False, "ImageMagick magick not found"
    cmd = ["magick", "-background", "none", str(svg_path), str(out_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()[:500]
    return True, None


def clean_raster_for_vtracer(input_path: Path, out_path: Path, colors: int = 8) -> Path:
    image = Image.open(input_path).convert("RGBA")
    rgba = np.array(image)
    alpha = rgba[:, :, 3]
    foreground = alpha >= 32
    if not np.any(foreground):
        image.save(out_path)
        return out_path

    rgb = rgba[:, :, :3].copy()
    rgb = cv2.medianBlur(rgb, 3)
    samples = cv2.cvtColor(rgb[foreground].reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    sample_count = len(samples)
    if sample_count > 60000:
        idx = np.linspace(0, sample_count - 1, 60000).astype(np.int64)
        fit_samples = samples[idx].astype(np.float32)
    else:
        fit_samples = samples.astype(np.float32)

    unique_count = len(np.unique(fit_samples.astype(np.uint8), axis=0))
    cluster_count = min(colors, unique_count, len(fit_samples))
    if cluster_count > 1:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.4)
        _compactness, _labels, centers = cv2.kmeans(
            fit_samples,
            cluster_count,
            None,
            criteria,
            3,
            cv2.KMEANS_PP_CENTERS,
        )
        all_samples = samples.astype(np.float32)
        distances = np.linalg.norm(all_samples[:, None, :] - centers[None, :, :], axis=2)
        nearest = distances.argmin(axis=1)
        quant_lab = centers[nearest].astype(np.uint8).reshape(1, -1, 3)
        quant_rgb = cv2.cvtColor(quant_lab, cv2.COLOR_LAB2RGB).reshape(-1, 3)
        rgb[foreground] = quant_rgb

    # Remove tiny alpha islands introduced by segmentation noise.
    binary = foreground.astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)
    min_area = max(10, int(binary.sum() * 0.002))
    for label_id in range(1, num_labels):
        if stats[label_id, cv2.CC_STAT_AREA] >= min_area:
            cleaned[labels == label_id] = 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

    out = np.zeros_like(rgba)
    out[:, :, :3] = rgb
    out[:, :, 3] = (cleaned * 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(out_path)
    return out_path


def run_vtracer(input_path: Path, out_svg: Path, clean: bool = False, poster: bool = False) -> tuple[bool, str | None]:
    try:
        import vtracer

        source_path = input_path
        if clean or poster:
            cleaned_path = out_svg.parent.parent.parent / "tmp" / f"{input_path.stem}__{'poster' if poster else 'clean'}.png"
            source_path = clean_raster_for_vtracer(input_path, cleaned_path, colors=6 if poster else 8)

        vtracer.convert_image_to_svg_py(
            str(source_path),
            str(out_svg),
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=12 if poster else (8 if clean else 4),
            color_precision=4 if poster else (5 if clean else 6),
            layer_difference=32 if poster else (24 if clean else 16),
            corner_threshold=70 if poster else 60,
            length_threshold=8.0 if poster else (6.0 if clean else 4.0),
            max_iterations=8 if poster else 10,
            splice_threshold=60 if poster else 45,
            path_precision=2 if poster else 3,
        )
        return out_svg.exists(), None if out_svg.exists() else "no SVG written"
    except Exception as exc:
        return False, repr(exc)[:500]


def write_alpha_pbm(input_path: Path, pbm_path: Path) -> None:
    image = Image.open(input_path).convert("RGBA")
    alpha = image.getchannel("A")
    # Potrace traces black pixels. Foreground alpha becomes black, transparent background white.
    bitmap = alpha.point(lambda v: 0 if v >= 32 else 255, mode="1")
    bitmap.save(pbm_path)


def run_potrace(input_path: Path, out_svg: Path, work_dir: Path) -> tuple[bool, str | None]:
    if not shutil.which("potrace"):
        return False, "potrace not found"
    pbm_path = work_dir / f"{input_path.stem}.pbm"
    write_alpha_pbm(input_path, pbm_path)
    cmd = ["potrace", str(pbm_path), "-s", "--tight", "--turdsize", "2", "-o", str(out_svg)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()[:500]
    return out_svg.exists(), None if out_svg.exists() else "no SVG written"


def run_autotrace(input_path: Path, out_svg: Path) -> tuple[bool, str | None]:
    if not shutil.which("autotrace"):
        return False, "autotrace not found"
    ppm_path = out_svg.parent.parent.parent / "tmp" / f"{input_path.stem}__autotrace.ppm"
    flattened = Image.open(input_path).convert("RGBA")
    bg = Image.new("RGBA", flattened.size, (255, 255, 255, 255))
    bg.alpha_composite(flattened)
    bg.convert("RGB").save(ppm_path)
    cmd = [
        "autotrace",
        str(ppm_path),
        "--output-format",
        "svg",
        "--background-color",
        "FFFFFF",
        "--color-count",
        "10",
        "--despeckle-level",
        "2",
        "--output-file",
        str(out_svg),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout).strip()[:500]
    except subprocess.TimeoutExpired:
        return False, "autotrace timed out"
    return out_svg.exists(), None if out_svg.exists() else "no SVG written"


def write_imagetracer_node_script(script_path: Path, package_dir: Path) -> None:
    script_path.write_text(
        f"""
const fs = require('fs');
const PNG = require('{package_dir / "node_modules" / "pngjs"}').PNG;
const ImageTracer = require('{package_dir / "node_modules" / "imagetracerjs"}');

const input = process.argv[2];
const output = process.argv[3];
const buffer = fs.readFileSync(input);
const png = PNG.sync.read(buffer);
const svg = ImageTracer.imagedataToSVG({{
  width: png.width,
  height: png.height,
  data: png.data
}}, {{
  ltres: 1,
  qtres: 1,
  pathomit: 8,
  colorsampling: 2,
  numberofcolors: 10,
  mincolorratio: 0.001,
  roundcoords: 2,
  viewbox: true,
  desc: false
}});
fs.writeFileSync(output, svg);
""".strip()
        + "\n",
        encoding="utf-8",
    )


def run_imagetracer(input_path: Path, out_svg: Path, node_script: Path) -> tuple[bool, str | None]:
    proc = subprocess.run(["node", str(node_script), str(input_path), str(out_svg)], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()[:500]
    return out_svg.exists(), None if out_svg.exists() else "no SVG written"


def run_method(method: str, input_path: Path, out_dir: Path, node_script: Path) -> MethodResult:
    svg_path = out_dir / "svg" / method / f"{input_path.stem}.svg"
    render_path = out_dir / "renders" / method / f"{input_path.stem}.png"
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    render_path.parent.mkdir(parents=True, exist_ok=True)

    if method == "vtracer":
        ok, error = run_vtracer(input_path, svg_path)
    elif method == "vtracer_clean":
        ok, error = run_vtracer(input_path, svg_path, clean=True)
    elif method == "vtracer_poster":
        ok, error = run_vtracer(input_path, svg_path, clean=True, poster=True)
    elif method == "imagetracerjs":
        ok, error = run_imagetracer(input_path, svg_path, node_script)
    elif method == "potrace_mask":
        ok, error = run_potrace(input_path, svg_path, out_dir / "tmp")
    elif method == "autotrace":
        ok, error = run_autotrace(input_path, svg_path)
    else:
        ok, error = False, f"unknown method: {method}"

    rendered = None
    if ok:
        render_ok, render_error = render_svg(svg_path, render_path)
        if render_ok:
            rendered = str(render_path)
        else:
            error = f"render failed: {render_error}"
    return MethodResult(
        method=method,
        ok=ok,
        svg=str(svg_path) if ok else None,
        render=rendered,
        bytes=svg_path.stat().st_size if ok and svg_path.exists() else None,
        error=error,
    )


def flatten_on_checker(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path or not path.exists():
        return Image.new("RGB", size, (250, 250, 250))
    image = Image.open(path).convert("RGBA")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    bg = Image.new("RGBA", image.size, (245, 245, 245, 255))
    bg.alpha_composite(image)
    return bg.convert("RGB")


def write_contact_sheet(results: list[VectorizedCandidate], out_path: Path) -> None:
    cols = 1 + len(METHODS)
    tile_w, tile_h = 230, 210
    header_h = 34
    rows = len(results) + 1
    sheet = Image.new("RGB", (cols * tile_w, header_h + rows * tile_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("Arial.ttf", 12)
        bold = ImageFont.truetype("Arial Bold.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        bold = font

    headers = ["original", *METHODS]
    for col, header in enumerate(headers):
        draw.text((col * tile_w + 8, 10), header, fill=(0, 0, 0), font=bold)

    for row, item in enumerate(results):
        y = header_h + row * tile_h
        paths = [Path(item.source_cutout)]
        method_by_name = {m.method: m for m in item.methods}
        for method in METHODS:
            render = method_by_name.get(method).render if method_by_name.get(method) else None
            paths.append(Path(render) if render else None)

        for col, path in enumerate(paths):
            x = col * tile_w
            draw.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline=(220, 220, 220))
            if path and path.exists():
                img = flatten_on_checker(path, (tile_w - 18, tile_h - 58))
                sheet.paste(img, (x + (tile_w - img.width) // 2, y + 8))
            else:
                draw.text((x + 8, y + 70), "failed/skipped", fill=(150, 0, 0), font=font)

        draw.text((8, y + tile_h - 42), item.tier, fill=(0, 0, 0), font=font)
        draw.text((8, y + tile_h - 24), f"{item.mask_key} {Path(item.source_image).name[:28]}", fill=(60, 60, 60), font=font)
        for col, method in enumerate(METHODS, start=1):
            m = method_by_name[method]
            label = f"{m.bytes or 0}b" if m.ok else (m.error or "failed")[:24]
            draw.text((col * tile_w + 8, y + tile_h - 24), label, fill=(60, 60, 60), font=font)

    sheet.save(out_path, quality=92)


def main() -> int:
    args = build_parser().parse_args()
    out_dir = args.output_dir
    for child in ("inputs", "svg", "renders", "tmp"):
        (out_dir / child).mkdir(parents=True, exist_ok=True)

    package_dir = Path("test-materials/output/vectorization-eval/npm-tools").resolve()
    node_script = out_dir / "tmp" / "run_imagetracer.js"
    write_imagetracer_node_script(node_script, package_dir)

    results: list[VectorizedCandidate] = []
    for idx, candidate in enumerate(selected_candidates(args.candidates_json, args.limit)):
        source = Path(candidate["cutout"])
        input_path = out_dir / "inputs" / f"{idx:03d}__{source.name}"
        shutil.copyfile(source, input_path)
        method_results = [run_method(method, input_path, out_dir, node_script) for method in METHODS]
        results.append(
            VectorizedCandidate(
                id=f"{idx:03d}",
                tier=candidate["candidate_tier"],
                source_cutout=str(input_path),
                source_image=candidate["image"],
                mask_key=candidate["mask_key"],
                methods=method_results,
            )
        )

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "candidates_json": str(args.candidates_json),
        "output_dir": str(out_dir),
        "methods": list(METHODS),
        "results": [
            {
                **{k: v for k, v in asdict(item).items() if k != "methods"},
                "methods": [asdict(m) for m in item.methods],
            }
            for item in results
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_contact_sheet(results, out_dir / "contact_sheet.jpg")

    ok_counts = {
        method: sum(1 for item in results for m in item.methods if m.method == method and m.ok)
        for method in METHODS
    }
    print(f"vectorized {len(results)} candidates -> {out_dir}")
    print(ok_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
