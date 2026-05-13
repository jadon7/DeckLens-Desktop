import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main():
    with tempfile.TemporaryDirectory(prefix="decklens-startup-") as data_dir:
        os.environ["DECKLENS_DATA_DIR"] = data_dir
        os.environ.setdefault("DECKLENS_INPAINT_BACKEND", "opencv")

        import app  # noqa: F401

        loaded_heavy_modules = [
            name
            for name in ("torch", "paddle", "paddleocr", "simple_lama_inpainting", "segment_anything")
            if name in sys.modules
        ]
        assert not loaded_heavy_modules, f"heavy modules loaded at startup: {loaded_heavy_modules}"

    print("startup lightweight check passed")


if __name__ == "__main__":
    main()
