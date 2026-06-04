import mimetypes
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / f"retriflow-tika-smoke-{uuid.uuid4().hex}.db"

    os.environ["RETRIFLOW_DB_PATH"] = str(db_path)
    os.environ["RETRIFLOW_TIKA_ENABLED"] = "true"
    os.environ["RETRIFLOW_TIKA_ENDPOINT"] = "http://127.0.0.1:9998"
    os.environ["RETRIFLOW_TIKA_OCR_ENABLED"] = "true"
    os.environ["RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT"] = "http://127.0.0.1:9889"

    from core.config import get_settings
    from main import create_app

    get_settings.cache_clear()
    client = TestClient(create_app())

    samples_dir = ROOT / "tools" / "tika" / "samples"
    try:
        for path in sorted(samples_dir.iterdir()):
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            with path.open("rb") as file_obj:
                response = client.post(
                    "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
                    files={"file": (path.name, file_obj.read(), content_type)},
                )
            print(f"{path.name}: upload status={response.status_code}")
            if response.status_code != 201:
                print(response.text)
                continue

            document_id = response.json()["id"]
            blocks_response = client.get(
                f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/structured-blocks"
            )
            print(f"{path.name}: blocks status={blocks_response.status_code}")
            if blocks_response.status_code != 200:
                print(blocks_response.text)
                continue

            payload = blocks_response.json()["items"]
            print(f"{path.name}: block_count={len(payload)}")
            for block in payload[:6]:
                summary = {
                    "block_type": block["block_type"],
                    "page_number": block.get("page_number"),
                    "text": (block.get("text") or "")[:80],
                    "headers": block.get("headers", []),
                    "row_count": block.get("row_count"),
                }
                print(json.dumps(summary, ensure_ascii=False))
            print("-" * 60)
    finally:
        client.close()
        get_settings.cache_clear()
        try:
            temp_dir.cleanup()
        except PermissionError:
            pass


if __name__ == "__main__":
    main()
