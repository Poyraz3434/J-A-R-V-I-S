"""Özellik 10 — ResearchEngine mod testleri (çevrimdışı, enjekte edilen sahte arama)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import research_engine
from research_engine import (
    MODES, ResearchEngine, Source, compute_budget, parse_requested_pages,
    requires_research, resolve_pages,
)
from research_ui import RoundCountdownWidget, should_show_countdown

# Güvenilir / güvensiz örnek alanlar
GOV_URL = "https://www.nature.com/articles/sample"
OFFICIAL_URL = "https://tubitak.gov.tr/haber/1"
FORUM_URL = "https://www.reddit.com/r/xyz/comments/1"
BLOG_URL = "https://example-fanblog.blogspot.com/post/1"


def _sources_for(mode: str) -> list[Source]:
    """Örnek arama sonucu havuzu (güvenilir + güvensiz karışık)."""
    return [
        Source(url=GOV_URL, title="Bilimsel çalışma", snippet="-peer reviewed-"),
        Source(url=OFFICIAL_URL, title="Resmi duyuru", snippet="kurum duyurusu"),
        Source(url="https://reuters.com/article/x", title="Haber", snippet="son dakika"),
        Source(url=FORUM_URL, title="Forum yorumu", snippet="bence öyle"),
        Source(url=BLOG_URL, title="Kişisel blog", snippet="şahsi görüş"),
        Source(url="https://quora.com/q/1", title="Soru-cevap", snippet="bilinmiyor"),
    ]


class _FakeSearch:
    """search_fn sahtesi: çağrı sayısını kaydeder."""

    def __init__(self, pool: list[Source] | None = None):
        self.calls = 0
        self.pool = pool

    def __call__(self, query: str, max_results: int, offset: int) -> list[Source]:
        self.calls += 1
        pool = self.pool if self.pool is not None else _sources_for("pro")
        return pool[offset:offset + max_results]


class ModeParamTests(unittest.TestCase):
    def test_mode_table_matches_spec(self):
        """Mod tablosu spec'e uymalı (kaynak aralıkları, bütçe, güvenilirlik)."""
        lite, flash, pro, deep = (MODES["flash_lite"], MODES["flash"],
                                  MODES["pro"], MODES["deep"])
        self.assertEqual(lite.max_sources, 6)
        self.assertLessEqual(lite.max_total_s, 5.0)           # ≤5 sn
        self.assertEqual(flash.min_sources, 4)
        self.assertEqual(flash.max_sources, 10)
        self.assertLessEqual(compute_budget(flash, 10), 10.5)  # ~10 sn
        self.assertEqual(pro.max_sources, 20)
        self.assertLessEqual(compute_budget(pro, 20), 40.5)    # ≤40 sn
        self.assertTrue(pro.reliability)
        self.assertTrue(deep.reliability)
        self.assertGreaterEqual(deep.estimate_s, 600)          # 10 dk+
        self.assertLessEqual(deep.estimate_s, 900)             # 15 dk-
        self.assertFalse(lite.reliability)
        self.assertFalse(flash.reliability)

    def test_user_page_override_wins(self):
        """Kullanıcı '3 sayfa' derse mod varsayılanı geçersiz kalır."""
        self.assertEqual(resolve_pages(MODES["flash_lite"], 3.0), 3.0)
        self.assertEqual(resolve_pages(MODES["flash"], None),
                         MODES["flash"].target_pages)

    def test_pages_clamped_to_20(self):
        """Hiçbir mod 20 sayfayı aşamaz (deep üst sınırı genel tavan)."""
        self.assertEqual(resolve_pages(MODES["deep"], 50), 20.0)
        self.assertEqual(resolve_pages(MODES["flash"], 0), 1.0)

    def test_parse_requested_pages(self):
        self.assertEqual(parse_requested_pages("bunu 3 sayfa rapor yap"), 3.0)
        self.assertEqual(parse_requested_pages("yaklaşık 2,5 sayfa olsun"), 2.5)
        self.assertIsNone(parse_requested_pages("hava nasıl"))

    def test_requires_research_heuristic(self):
        """Araştırmasız genel bilgi → False; güncellik/araştırma → True."""
        self.assertFalse(requires_research("2+2 kaç"))
        self.assertFalse(requires_research("photosynthesis nedir"))
        self.assertTrue(requires_research("bugün son dakika haberleri"))
        self.assertTrue(requires_research("thya hissesi güncel fiyat"))
        self.assertTrue(requires_research("bu konuyu araştır"))


class ReliabilityFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = ResearchEngine(search_fn=_FakeSearch())

    def test_default_search_registers_and_closes_streaming_response(self):
        response = mock.Mock()
        response.text = "<html></html>"
        registered = []
        with mock.patch.object(
            research_engine, "HTTP_SESSION"
        ) as session:
            session.get.return_value = response
            results = research_engine._ddg_search(
                "query", response_callback=registered.append
            )

        self.assertEqual(results, [])
        self.assertTrue(session.get.call_args.kwargs["stream"])
        self.assertEqual(registered, [response, None])
        response.close.assert_called_once()

    def test_untrusted_sources_excluded_from_main_list(self):
        """Güvensiz kaynaklar (forum/blog) ana rapor listesine girmez."""
        report = self.engine.research("güncel bilim haberleri", "pro")
        urls = [s.url for s in report.sources]
        self.assertIn(GOV_URL, urls)
        self.assertNotIn(FORUM_URL, urls)
        self.assertNotIn(BLOG_URL, urls)
        self.assertTrue(report.excluded, "Elemenen kaynak listesi dolu olmalı")

    def test_all_untrusted_shows_filters_section(self):
        """Sadece güvensiz kaynak varsa: Filtreler bölümü açıksa görünür."""
        fake = _FakeSearch(pool=[
            Source(url=FORUM_URL, title="Forum", snippet="yorum"),
            Source(url=BLOG_URL, title="Blog", snippet="görüş"),
        ])
        engine = ResearchEngine(search_fn=fake)
        report = engine.research("x hakkında", "pro", show_filters=True)
        self.assertEqual(report.sources, [])
        self.assertIn("Filtreler", report.text)
        self.assertIn("Hayır", report.text)

    def test_filters_hidden_when_setting_off(self):
        """Ayar kapalıyken Filtreler bölümü raporda görünmez + bilgi notu."""
        fake = _FakeSearch(pool=[Source(url=FORUM_URL, title="Forum", snippet="y")])
        engine = ResearchEngine(search_fn=fake)
        report = engine.research("x", "pro", show_filters=False)
        self.assertEqual(report.sources, [])
        self.assertNotIn("Filtreler", report.text)
        self.assertIn("gizlendi", report.text)

    def test_flash_lite_skips_search_for_general_knowledge(self):
        """Araştırmasız soruda Flash Lite arama yapmaz (anında cevap)."""
        fake = _FakeSearch()
        engine = ResearchEngine(search_fn=fake)
        report = engine.research("2+2 kaç", "flash_lite")
        self.assertEqual(fake.calls, 0)
        self.assertTrue(report.direct)

    def test_flash_mode_respects_max_sources(self):
        """Flash modu 10 kaynağı aşmaz, 4 kaynak altına inmez (varsa)."""
        fake = _FakeSearch(pool=[
            Source(url=f"https://site{i}.com/{i}", title=f"r{i}", snippet="s")
            for i in range(30)
        ])
        engine = ResearchEngine(search_fn=fake)
        report = engine.research("güncel konu", "flash")
        self.assertLessEqual(len(report.sources), 10)
        self.assertGreaterEqual(len(report.sources), 4)


class CountdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_threshold(self):
        """≥5 dk göster; altındaki Pro/Late/Flash göstermez."""
        self.assertTrue(should_show_countdown(600))
        self.assertFalse(should_show_countdown(40))
        self.assertFalse(should_show_countdown(299))

    def test_countdown_ticks_down_and_stops(self):
        widget = RoundCountdownWidget()
        widget.start_countdown(300)
        self.assertTrue(widget.isVisible())
        first = widget.remaining()
        QTest.qWait(1200)
        self.assertLessEqual(widget.remaining(), first - 1)
        widget.stop_countdown()
        self.assertFalse(widget.isVisible())


if __name__ == "__main__":
    unittest.main()
