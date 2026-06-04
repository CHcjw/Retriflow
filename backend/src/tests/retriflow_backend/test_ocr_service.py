import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[4]
OCR_APP_PATH = PROJECT_ROOT / "tools" / "ocr" / "app.py"


def _load_ocr_module():
    module_name = "retriflow_ocr_app"
    if module_name in sys.modules:
        return sys.modules[module_name]

    sys.modules.setdefault(
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda *args, **kwargs: ""),
    )

    spec = importlib.util.spec_from_file_location(module_name, OCR_APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RetriFlowOcrServiceTests(unittest.TestCase):
    def test_extract_captions_accepts_pdf_payload_and_ocrs_rendered_pages(self) -> None:
        ocr_module = _load_ocr_module()
        client = TestClient(ocr_module.app)

        with (
            patch.object(
                ocr_module,
                "_extract_pdf_page_images",
                return_value=[(1, Image.new("RGB", (320, 120), "white"))],
            ) as render_mock,
            patch.object(
                ocr_module.pytesseract,
                "image_to_string",
                return_value="Figure 1 PDF OCR Caption",
            ) as ocr_mock,
        ):
            response = client.post(
                "/ocr/captions",
                files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"pages": [{"page_number": 1, "captions": ["Figure 1 PDF OCR Caption"]}]},
        )
        render_mock.assert_called_once()
        ocr_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
