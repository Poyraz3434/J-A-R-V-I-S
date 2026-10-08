"""Özellik 1 — Sunum builder testleri (fallback zinciri + outline kuralları)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import presentation_builder as pb


class OutlineTests(unittest.TestCase):
    def test_default_slide_count(self):
        """Varsayılan 9 slayt (8-10 aralığı)."""
        self.assertEqual(pb.DEFAULT_SLIDES, 9)
        outline = pb.generate_outline("Yapay zeka", pb.DEFAULT_SLIDES)
        self.assertTrue(outline.slides)

    def test_long_bullets_split_to_multiple_slides(self):
        """Slayt başına >6 madde otomatik bölünmeli."""
        bullets = [f"madde {i}" for i in range(10)]
        outline = pb.normalize_outline("Konu", [{"title": "T", "bullets": bullets}], 12)
        self.assertEqual(len(outline.slides), 2)          # 6 + 4
        self.assertLessEqual(len(outline.slides[0].bullets), pb.MAX_BULLETS)
        self.assertEqual(len(outline.slides[1].bullets), 4)

    def test_template_uses_user_content(self):
        """Kullanıcı içeriği şablonda madde olarak kullanılır."""
        outline = pb.template_outline("X", 8, content="birinci nokta\nikinci nokta")
        all_bullets = [b for s in outline.slides for b in s.bullets]
        self.assertIn("birinci nokta", all_bullets)
        self.assertIn("ikinci nokta", all_bullets)


class FallbackChainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pptx_path_used_first(self):
        """1. adım: python-pptx varsa .pptx üretilir (başlık+içindekiler+kapanış)."""
        r = pb.build_presentation("Test Konusu", 6, out_dir=self.out)
        self.assertTrue(r.ok, r.message)
        self.assertEqual(r.method, "pptx")
        path = Path(r.path)
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes()[:2], b"PK")   # pptx = zip
        # başlık + içindekiler + kapanış + içerik
        self.assertGreaterEqual(r.slide_count, 6)

    def test_fallback_to_images_when_pptx_fails(self):
        """pptx tutmazsa → Canva (anahtar yok) → görsel seti (kullanıcıya bildirilir)."""
        with mock.patch.object(pb, "_build_pptx",
                               side_effect=ImportError("blocked")):
            r = pb.build_presentation("Fallback Konu", 5, out_dir=self.out)
        self.assertTrue(r.ok, r.message)
        self.assertEqual(r.method, "images")
        self.assertIn("FALLBACK", r.message)
        self.assertIn("Canva", r.message)                # atlanan adım sebebi
        zip_path = Path(r.path)
        self.assertTrue(zip_path.exists())
        self.assertGreaterEqual(r.slide_count, 5)        # başlık+içindekiler+...

    def test_content_overflow_produces_more_slides(self):
        """Uzun içerik (>6 madde) birden fazla slayta bölünür."""
        content = "\n".join(f"madde {i}" for i in range(14))
        r = pb.build_presentation("Bölünmüş", 20, content=content, out_dir=self.out)
        self.assertTrue(r.ok, r.message)
        # normalize: 14 madde → 3 içerik slaytı + 3 sabit ≥6 toplam
        self.assertGreaterEqual(r.slide_count, 6)


if __name__ == "__main__":
    unittest.main()
