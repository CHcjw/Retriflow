import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowTikaSampleGenerationTests(unittest.TestCase):
    def test_docx_sample_contains_embedded_image(self) -> None:
        module = self._load_sample_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            module.SAMPLES_DIR = Path(temp_dir)
            path = module.create_docx_sample()

            with ZipFile(path) as archive:
                media_entries = [name for name in archive.namelist() if name.startswith("word/media/")]

        self.assertGreaterEqual(len(media_entries), 1)

    def test_docx_sample_uses_normalized_caption_prefix(self) -> None:
        module = self._load_sample_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            module.SAMPLES_DIR = Path(temp_dir)
            path = module.create_docx_sample()

            with ZipFile(path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")

        root = ET.fromstring(document_xml)
        text_nodes = [node.text for node in root.iter() if node.text]
        joined = " ".join(text_nodes)
        self.assertIn("图1 RetriFlow document parsing overview", joined)

    def test_pdf_sample_contains_image_object(self) -> None:
        module = self._load_sample_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            module.SAMPLES_DIR = Path(temp_dir)
            path = module.create_pdf_sample()
            payload = path.read_bytes()

        self.assertIn(b"/Subtype /Image", payload)

    def test_main_creates_image_only_samples(self) -> None:
        module = self._load_sample_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            module.SAMPLES_DIR = Path(temp_dir)
            module.main()

            generated = sorted(path.name for path in Path(temp_dir).iterdir())

        self.assertIn("retriflow-image-only.docx", generated)
        self.assertIn("retriflow-image-only.pdf", generated)

    @staticmethod
    def _load_sample_module():
        module_path = PROJECT_ROOT / "tools" / "tika" / "create_tika_samples.py"
        spec = importlib.util.spec_from_file_location("retriflow_tika_samples", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module


if __name__ == "__main__":
    unittest.main()
