import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import requests


def main():
    original_path = engine.SAM_CHECKPOINT_PATH
    original_get = requests.get
    original_min = os.environ.get("DECKLENS_SAM_MIN_BYTES")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "sam_vit_h_4b8939.pth")
        engine.SAM_CHECKPOINT_PATH = checkpoint_path
        os.environ["DECKLENS_SAM_MIN_BYTES"] = "10"

        with open(checkpoint_path, "wb") as f:
            f.write(b"bad")

        class FakeResponse:
            status_code = 200
            headers = {"Content-Length": "10"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield b"01234"
                yield b"56789"

        def fake_get(*_args, **_kwargs):
            return FakeResponse()

        requests.get = fake_get

        result = engine._download_sam_checkpoint()

        assert result == checkpoint_path
        assert os.path.exists(checkpoint_path)
        assert os.path.getsize(checkpoint_path) == 10
        assert not os.path.exists(f"{checkpoint_path}.part")

    engine.SAM_CHECKPOINT_PATH = original_path
    requests.get = original_get
    if original_min is None:
        os.environ.pop("DECKLENS_SAM_MIN_BYTES", None)
    else:
        os.environ["DECKLENS_SAM_MIN_BYTES"] = original_min


if __name__ == "__main__":
    main()
