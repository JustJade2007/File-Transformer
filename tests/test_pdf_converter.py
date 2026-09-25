"""Tests for expanded PDF conversion and multi-page per-page export."""
import os
import shutil
import tempfile
import unittest
from PIL import Image
import pypdf

from core.converters.documents import DocumentConverter
from core.converters.base import ConversionResult
from core.engine import ConversionEngine, ConversionTask, TaskStatus
from core.registry import FormatRegistry


class TestPDFConverter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.converter = DocumentConverter()

        # Create a 3-page test PDF with text and shapes
        self.multi_page_pdf = os.path.join(self.temp_dir, "sample_doc.pdf")
        self._create_sample_pdf(self.multi_page_pdf, num_pages=3)

        # Create a 1-page test PDF
        self.single_page_pdf = os.path.join(self.temp_dir, "single_doc.pdf")
        self._create_sample_pdf(self.single_page_pdf, num_pages=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_pdf(self, path: str, num_pages: int):
        writer = pypdf.PdfWriter()
        for i in range(num_pages):
            tmp_p = f"{path}_tmp_{i}.pdf"
            self.converter._minimal_pdf_write(
                f"Page {i+1} content:\nThis is line 1 of page {i+1}.\nThis is line 2 of page {i+1}.",
                tmp_p,
                f"Doc {i+1}",
            )
            tmp_reader = pypdf.PdfReader(tmp_p)
            writer.add_page(tmp_reader.pages[0])
            if os.path.exists(tmp_p):
                os.remove(tmp_p)
        with open(path, "wb") as f:
            writer.write(f)

    def test_registry_supports_expanded_pdf_targets(self):
        registry = FormatRegistry()
        targets = registry.get_valid_targets("pdf")
        all_targets = set()
        for tlist in targets.values():
            all_targets.update(tlist)

        expected = {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "docx", "md", "html", "txt", "pdf"}
        self.assertTrue(expected.issubset(all_targets), f"Missing targets: {expected - all_targets}")

    def test_multipage_pdf_to_png_exports_per_page(self):
        """Converting a 3-page PDF to PNG must export a file per page."""
        target_path = os.path.join(self.temp_dir, "sample_doc.png")
        result = self.converter.convert(self.multi_page_pdf, target_path, "png")

        self.assertTrue(result.success, f"Conversion failed: {result.error_message}")
        self.assertEqual(len(result.output_paths), 3)

        expected_files = [
            os.path.join(self.temp_dir, "sample_doc_page_1.png"),
            os.path.join(self.temp_dir, "sample_doc_page_2.png"),
            os.path.join(self.temp_dir, "sample_doc_page_3.png"),
        ]

        for ef in expected_files:
            self.assertTrue(os.path.exists(ef), f"Expected file does not exist: {ef}")
            with Image.open(ef) as img:
                self.assertEqual(img.format, "PNG")
                self.assertGreater(img.width, 100)
                self.assertGreater(img.height, 100)

        self.assertEqual(result.output_paths, expected_files)
        self.assertEqual(result.output_path, expected_files[0])

    def test_singlepage_pdf_to_png_exports_single_file(self):
        """Converting a 1-page PDF to PNG should output single_doc.png directly."""
        target_path = os.path.join(self.temp_dir, "single_doc.png")
        result = self.converter.convert(self.single_page_pdf, target_path, "png")

        self.assertTrue(result.success, f"Conversion failed: {result.error_message}")
        self.assertEqual(len(result.output_paths), 1)
        self.assertEqual(result.output_path, target_path)
        self.assertTrue(os.path.exists(target_path))

        with Image.open(target_path) as img:
            self.assertEqual(img.format, "PNG")

    def test_multipage_pdf_to_jpg_exports_per_page(self):
        """Converting a 3-page PDF to JPG must export 3 valid JPEG images."""
        target_path = os.path.join(self.temp_dir, "sample_doc.jpg")
        result = self.converter.convert(self.multi_page_pdf, target_path, "jpg")

        self.assertTrue(result.success, f"Conversion failed: {result.error_message}")
        self.assertEqual(len(result.output_paths), 3)

        for i in range(1, 4):
            path = os.path.join(self.temp_dir, f"sample_doc_page_{i}.jpg")
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as img:
                self.assertEqual(img.format, "JPEG")

    def test_multipage_pdf_to_webp_and_bmp(self):
        """Converting to WEBP and BMP must export per-page files."""
        # WEBP
        webp_target = os.path.join(self.temp_dir, "sample_doc.webp")
        res_webp = self.converter.convert(self.multi_page_pdf, webp_target, "webp")
        self.assertTrue(res_webp.success)
        self.assertEqual(len(res_webp.output_paths), 3)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "sample_doc_page_1.webp")))

        # BMP
        bmp_target = os.path.join(self.temp_dir, "sample_doc.bmp")
        res_bmp = self.converter.convert(self.multi_page_pdf, bmp_target, "bmp")
        self.assertTrue(res_bmp.success)
        self.assertEqual(len(res_bmp.output_paths), 3)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "sample_doc_page_1.bmp")))

    def test_multipage_pdf_to_tiff_multipage(self):
        """Converting to TIFF with default options creates a single multi-page TIFF file."""
        target_path = os.path.join(self.temp_dir, "sample_doc.tiff")
        result = self.converter.convert(self.multi_page_pdf, target_path, "tiff")

        self.assertTrue(result.success, f"Conversion failed: {result.error_message}")
        self.assertEqual(len(result.output_paths), 1)
        self.assertTrue(os.path.exists(target_path))

        with Image.open(target_path) as img:
            self.assertEqual(img.format, "TIFF")
            self.assertEqual(getattr(img, "n_frames", 1), 3)

    def test_multipage_pdf_to_docx(self):
        """Converting multi-page PDF to DOCX preserves content and page boundaries."""
        target_path = os.path.join(self.temp_dir, "sample_doc.docx")
        result = self.converter.convert(self.multi_page_pdf, target_path, "docx")

        self.assertTrue(result.success, f"Conversion failed: {result.error_message}")
        self.assertTrue(os.path.exists(target_path))
        self.assertGreater(os.path.getsize(target_path), 0)

        import docx
        doc = docx.Document(target_path)
        # Check paragraphs exist
        self.assertGreater(len(doc.paragraphs), 0)

    def test_multipage_pdf_to_md(self):
        """Converting multi-page PDF to Markdown preserves all pages."""
        target_path = os.path.join(self.temp_dir, "sample_doc.md")
        result = self.converter.convert(self.multi_page_pdf, target_path, "md")

        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(target_path))

        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("## Page 1", content)
        self.assertIn("## Page 2", content)
        self.assertIn("## Page 3", content)

    def test_multipage_pdf_to_html(self):
        """Converting multi-page PDF to HTML preserves all pages in structured sections."""
        target_path = os.path.join(self.temp_dir, "sample_doc.html")
        result = self.converter.convert(self.multi_page_pdf, target_path, "html")

        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(target_path))

        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('id="page-1"', content)
        self.assertIn('id="page-2"', content)
        self.assertIn('id="page-3"', content)

    def test_page_range_filtering(self):
        """Option page_range selects only specified pages."""
        target_path = os.path.join(self.temp_dir, "sample_range.png")
        result = self.converter.convert(
            self.multi_page_pdf,
            target_path,
            "png",
            options={"page_range": "2-3", "dpi": 150},
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.output_paths), 2)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "sample_range_page_2.png")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "sample_range_page_3.png")))
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "sample_range_page_1.png")))

    def test_engine_integration_multi_file_task(self):
        """Engine correctly executes task and sets output_paths and Done (N files)."""
        engine = ConversionEngine(max_workers=2)
        out_dir = os.path.join(self.temp_dir, "engine_out")

        task = ConversionTask(
            task_id="test_task_1",
            source_path=self.multi_page_pdf,
            target_format="png",
            output_dir=out_dir,
        )

        engine.submit(task)

        # Wait for task completion
        import time
        for _ in range(50):
            if task.status in (TaskStatus.DONE, TaskStatus.ERROR):
                break
            time.sleep(0.1)

        engine.shutdown(wait=True)

        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertEqual(task.status_text, "Done (3 files)")
        self.assertEqual(len(task.output_paths), 3)
        for p in task.output_paths:
            self.assertTrue(os.path.exists(p))

    def test_pdf_split_pages_to_pdf(self):
        """PDF to PDF with split_pages=True exports individual page PDFs."""
        target_path = os.path.join(self.temp_dir, "sample_split.pdf")
        result = self.converter.convert(
            self.multi_page_pdf,
            target_path,
            "pdf",
            options={"split_pages": True},
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.output_paths), 3)
        for i in range(1, 4):
            path = os.path.join(self.temp_dir, f"sample_split_page_{i}.pdf")
            self.assertTrue(os.path.exists(path))
            reader = pypdf.PdfReader(path)
            self.assertEqual(len(reader.pages), 1)

    def test_pdf_with_embedded_image(self):
        """PDF containing scanned/embedded images extracts images cleanly."""
        img_pdf = os.path.join(self.temp_dir, "scanned_doc.pdf")
        src_img = Image.new("RGB", (120, 120), (200, 50, 50))
        src_img.save(img_pdf, "PDF")

        target_png = os.path.join(self.temp_dir, "scanned_doc.png")
        result = self.converter.convert(img_pdf, target_png, "png")
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(target_png))
        with Image.open(target_png) as out_img:
            self.assertEqual(out_img.format, "PNG")
            self.assertEqual(out_img.size, (120, 120))

    def test_cli_runner_multipage_export(self):
        """Test invoking cli.py via subprocess to verify end-to-end command line output."""
        import subprocess
        import sys

        out_dir = os.path.join(self.temp_dir, "cli_test_dir")
        proc = subprocess.run(
            [sys.executable, "cli.py", "-i", self.multi_page_pdf, "-f", "png", "-o", out_dir],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"CLI stderr: {proc.stderr}")
        self.assertIn("3 files", proc.stdout)
        for i in range(1, 4):
            self.assertTrue(os.path.exists(os.path.join(out_dir, f"sample_doc_page_{i}.png")))


if __name__ == "__main__":
    unittest.main()

