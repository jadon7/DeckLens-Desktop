import io
import os
import tempfile
import time
import zipfile
from pathlib import Path
import sys

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def make_slide_image() -> bytes:
    image = Image.new("RGB", (480, 270), "#f7fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 34, 448, 74), fill="#0f172a")
    draw.text((48, 44), "DeckLens 2026", fill="#ffffff")
    draw.rectangle((56, 112, 210, 198), fill="#38bdf8")
    draw.ellipse((270, 104, 382, 216), fill="#f97316")
    draw.text((64, 220), "AI slide to editable PPTX", fill="#111827")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_slide_pdf(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        pdf_buffer = io.BytesIO()
        image.convert("RGB").save(pdf_buffer, format="PDF")
        return pdf_buffer.getvalue()


def wait_for_status(client, task_id: str, target_statuses: set[str], timeout: int = 240) -> dict:
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        response = client.get(f"/api/status/{task_id}")
        assert response.status_code == 200, response.get_data(as_text=True)
        data = response.get_json()
        last_status = data
        if data["status"] in target_statuses:
            return data
        if data["status"] == "error":
            raise AssertionError(data)
        time.sleep(1)
    raise TimeoutError(f"task {task_id} did not reach {target_statuses}; last={last_status}")


def assert_pptx_response(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_data()
    assert len(payload) > 1000
    with zipfile.ZipFile(io.BytesIO(payload)) as pptx:
        names = set(pptx.namelist())
        assert "ppt/presentation.xml" in names
        slide_names = [name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
        assert slide_names
        slide_xml = "\n".join(pptx.read(name).decode("utf-8", errors="ignore") for name in slide_names)
        assert "<a:t>" in slide_xml
        assert "sz=" in slide_xml


def submit_convert(client, file_bytes: bytes, filename: str, **fields) -> str:
    data = {"files": (io.BytesIO(file_bytes), filename)}
    data.update(fields)
    response = client.post("/api/convert", data=data, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["task_id"]


def main():
    with tempfile.TemporaryDirectory(prefix="decklens-flow-") as data_dir:
        os.environ["DECKLENS_DATA_DIR"] = data_dir
        os.environ["DECKLENS_DEVICE"] = "cpu"
        os.environ["DECKLENS_INPAINT_BACKEND"] = "opencv"
        os.environ.pop("DECKLENS_ENABLE_SAM", None)

        import app as decklens

        client = decklens.app.test_client()

        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.get_json()["ok"] is True

        home = client.get("/")
        assert home.status_code == 200
        assert b"DeckLens" in home.data

        invalid = client.post(
            "/api/convert",
            data={"files": (io.BytesIO(b"not an image"), "bad.txt")},
            content_type="multipart/form-data",
        )
        assert invalid.status_code == 400

        image_bytes = make_slide_image()

        standard_task = submit_convert(client, image_bytes, "slide.png", decompose_mode="none", inpaint_backend="local_mean")
        standard_done = wait_for_status(client, standard_task, {"done"})
        assert_pptx_response(client.get(standard_done["download_url"]))

        pdf_task = submit_convert(client, make_slide_pdf(image_bytes), "slide.pdf", decompose_mode="none", inpaint_backend="local_mean")
        pdf_done = wait_for_status(client, pdf_task, {"done"})
        assert_pptx_response(client.get(pdf_done["download_url"]))

        layer_task = submit_convert(
            client,
            image_bytes,
            "layered.png",
            decompose="true",
            decompose_mode="sam",
            inpaint_backend="local_mean",
        )
        preview_status = wait_for_status(client, layer_task, {"preview"})
        preview = client.get(preview_status["preview_url"])
        assert preview.status_code == 200, preview.get_data(as_text=True)
        preview_data = preview.get_json()
        assert preview_data["total_slides"] == 1
        assert len(preview_data["slides"]) == 1

        decisions = []
        for slide in preview_data["slides"]:
            decisions.append({
                "slide_index": slide["slide_index"],
                "keep": [mask["id"] for mask in slide["masks"]],
                "merge": [],
                "delete": [],
            })
        confirm = client.post(f"/api/confirm/{layer_task}", json={"slides": decisions})
        assert confirm.status_code == 200, confirm.get_data(as_text=True)
        layer_done = wait_for_status(client, layer_task, {"done"})
        assert_pptx_response(client.get(layer_done["download_url"]))

        print(f"main flow smoke passed; data_dir={Path(data_dir)}")


if __name__ == "__main__":
    main()
