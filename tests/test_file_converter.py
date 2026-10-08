"""Özellik 5 — Dosya Dönüştürücü testleri (Pillow + PyMuPDF ile gerçek dosya)."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from file_converter import convert_file, detect_ocr_needed


def _make_png(path: Path) -> Path:
    from PIL import Image
    Image.new("RGB", (32, 32), (200, 40, 40)).save(path, "PNG")
    return path


def _make_jpg(path: Path) -> Path:
    from PIL import Image
    Image.new("RGB", (32, 32), (40, 40, 200)).save(path, "JPEG", quality=90)
    return path


def _make_pdf(path: Path, pages: int = 1, text: str = "Merhaba dunya") -> Path:
    import fitz
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), f"{text} {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class ImageConversionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_png_to_pdf(self):
        src = _make_png(self.dir / "gorsel.png")
        r = convert_file(src, "pdf")
        self.assertTrue(r.ok, r.message)
        out = Path(r.outputs[0])
        self.assertTrue(out.exists())
        self.assertEqual(out.read_bytes()[:4], b"%PDF")

    def test_jpg_to_png_and_back(self):
        src = _make_jpg(self.dir / "foto.jpg")
        r = convert_file(src, "png")
        self.assertTrue(r.ok, r.message)
        self.assertEqual(Path(r.outputs[0]).read_bytes()[:4], b"\x89PNG")
        r2 = convert_file(r.outputs[0], "jpg")
        self.assertTrue(r2.ok, r2.message)

    def test_same_format_noop(self):
        src = _make_png(self.dir / "a.png")
        r = convert_file(src, "png")
        self.assertTrue(r.ok)
        self.assertIn("zaten", r.message)


class PdfConversionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pdf_to_text(self):
        src = _make_pdf(self.dir / "belge.pdf", text="Merhaba dunya")
        r = convert_file(src, "txt")
        self.assertTrue(r.ok, r.message)
        text = Path(r.outputs[0]).read_text(encoding="utf-8")
        self.assertIn("Merhaba", text)
        self.assertFalse(r.ocr_needed)

    def test_multipage_pdf_to_images_order_and_zip(self):
        src = _make_pdf(self.dir / "coklu.pdf", pages=3)
        r = convert_file(src, "png")
        self.assertTrue(r.ok, r.message)
        zip_path = Path(r.outputs[0])
        self.assertTrue(zip_path.name.endswith(".zip"))
        with zipfile.ZipFile(zip_path) as zf:
            names = sorted(zf.namelist())
        self.assertEqual(len(names), 3)
        self.assertIn("_p001.png", names[0])   # sayfa sırası korunur
        self.assertIn("_p003.png", names[2])

    def test_corrupt_pdf_gives_meaningful_error(self):
        bad = self.dir / "bozuk.pdf"
        bad.write_bytes(b"bu bir pdf degil")
        r = convert_file(bad, "txt")
        self.assertFalse(r.ok)
        self.assertIn("bozuk veya şifreli", r.message)

    def test_detect_ocr_needed_on_image_only_pdf(self):
        # Metin katmanı olmayan (yalnız görsel içeren) PDF → OCR gerekir
        import fitz
        png = _make_png(self.dir / "only.png")
        img_doc = fitz.open()
        page = img_doc.new_page(width=200, height=200)
        page.insert_image(fitz.Rect(10, 10, 190, 190), filename=str(png))
        scanned = self.dir / "taranmis.pdf"
        img_doc.save(str(scanned))
        img_doc.close()
        self.assertTrue(detect_ocr_needed(scanned))
        with_text = _make_pdf(self.dir / "metinli.pdf")
        self.assertFalse(detect_ocr_needed(with_text))


class UnsupportedFormatTests(unittest.TestCase):
    def test_unsupported_source_lists_supported(self):
        with tempfile.TemporaryDirectory() as d:
            docx = Path(d) / "rapor.docx"
            docx.write_bytes(b"PK...fake")
            r = convert_file(docx, "pdf")
            self.assertFalse(r.ok)
            self.assertIn("Desteklenen", r.message)

    def test_unsupported_target_lists_supported(self):
        with tempfile.TemporaryDirectory() as d:
            png = _make_png(Path(d) / "a.png")
            r = convert_file(png, "docx")
            self.assertFalse(r.ok)
            self.assertIn("Desteklenen", r.message)

    def test_missing_file(self):
        r = convert_file("yok/olmayan.png", "pdf")
        self.assertFalse(r.ok)
        self.assertIn("bulunamadı", r.message)


if __name__ == "__main__":
    unittest.main()
