"""Özellik 7 — StatusColorController / StatusBorderWidget durum çerçevesi testleri."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from status_border import AppState, StatusBorderWidget, StatusColorController


def _app() -> QApplication:
    """Tek QApplication sağla (offscreen platformunda çalışır)."""
    return QApplication.instance() or QApplication([])


class StatusColorControllerTests(unittest.TestCase):
    """Durum makinesi: idle/busy/error/success + 12 sn yeşil kuralı."""

    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def setUp(self):
        self.ctl = StatusColorController()
        self.ctl.SUCCESS_MS = 400  # testi hızlandır (mantık aynı)

    def test_success_returns_to_idle_after_timer(self):
        """SUCCESS, süre dolunca idle'a dönmeli."""
        self.ctl.set_state(AppState.SUCCESS)
        self.assertIs(self.ctl.state, AppState.SUCCESS)
        QTest.qWait(self.ctl.SUCCESS_MS + 300)
        self.assertIs(self.ctl.state, AppState.IDLE)

    def test_new_busy_cancels_success_timer(self):
        """Yeni mesaj (BUSY) yeşil sayacı anında iptal etmeli (12 sn bekleme yok)."""
        self.ctl.set_state(AppState.SUCCESS)
        self.assertTrue(self.ctl._success_timer.isActive())
        self.ctl.set_state(AppState.BUSY)
        self.assertFalse(self.ctl._success_timer.isActive())
        self.assertIs(self.ctl.state, AppState.BUSY)
        QTest.qWait(self.ctl.SUCCESS_MS + 300)
        self.assertIs(self.ctl.state, AppState.BUSY)  # idle'a düşmedi

    def test_error_is_sticky(self):
        """ERROR başka duruma geçilene kadar sabit kalmalı."""
        self.ctl.set_state(AppState.ERROR)
        QTest.qWait(500)
        self.assertIs(self.ctl.state, AppState.ERROR)

    def test_error_cancels_success(self):
        """SUCCESS sırasında hata → kırmızıya dönülür, sayaç iptal."""
        self.ctl.set_state(AppState.SUCCESS)
        self.ctl.set_state(AppState.ERROR)
        QTest.qWait(600)
        self.assertIs(self.ctl.state, AppState.ERROR)

    def test_notify_idle_keeps_success(self):
        """core idle bildirimi success beklemesinde yeşili bozmamalı (12 sn kuralı)."""
        self.ctl.set_state(AppState.SUCCESS)
        self.ctl.notify_idle()
        self.assertIs(self.ctl.state, AppState.SUCCESS)

    def test_color_transition_is_smooth(self):
        """Renk aniden zıplamamalı; geçiş sırasında ara ton oluşmalı."""
        start = QColorTuple(self.ctl.color)
        self.ctl.set_state(AppState.BUSY)
        QTest.qWait(150)
        mid = QColorTuple(self.ctl.color)
        target = QColorTuple(self.ctl.COLORS[AppState.BUSY])
        self.assertNotEqual(mid, start)
        self.assertNotEqual(mid, target)
        QTest.qWait(self.ctl.TRANSITION_MS)
        settled = QColorTuple(self.ctl.color)
        self.assertEqual(settled, QColorTuple(self.ctl.COLORS[AppState.BUSY]))

    def test_state_changed_signal_no_duplicate(self):
        """Aynı duruma tekrar set → state_changed tekrarlanmamalı."""
        seen = []
        self.ctl.state_changed.connect(seen.append)
        self.ctl.set_state(AppState.BUSY)
        self.ctl.set_state(AppState.BUSY)
        self.assertEqual(seen, [AppState.BUSY.value])

    def test_unknown_state_ignored(self):
        """Bilinmeyen durum string'i çökmemeli, yok sayılmalı."""
        self.ctl.set_state("bogus")
        self.assertIs(self.ctl.state, AppState.IDLE)


def QColorTuple(color, with_alpha: bool = False):
    """QColor'ı karşılaştırılabilir tuple'a çevir (RGB veya RGBA)."""
    if with_alpha:
        return (color.red(), color.green(), color.blue(), color.alpha())
    return (color.red(), color.green(), color.blue())


class StatusBorderWidgetTests(unittest.TestCase):
    """Widget: yerleşim boşlukları + gerçekten çizim (offscreen grab)."""

    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def test_content_margins_match_border_width(self):
        ctl = StatusColorController()
        widget = StatusBorderWidget(ctl)
        widget.set_content(QWidget())
        margins = widget.layout().contentsMargins()
        width = StatusBorderWidget.CONTENT_INSET
        self.assertEqual(
            (margins.left(), margins.top(), margins.right(), margins.bottom()),
            (width, width, width, width),
        )

    def test_error_state_paints_all_edges_and_right_corners(self):
        """Dört kenar ve sağ köşeler de durum renginde görünür olmalı."""
        ctl = StatusColorController()
        widget = StatusBorderWidget(ctl)
        widget.set_content(QWidget())
        widget.resize(300, 200)
        widget.show()
        QTest.qWait(50)
        ctl.set_state(AppState.ERROR)
        QTest.qWait(ctl.TRANSITION_MS + 150)
        image = widget.grab().toImage()
        samples = {
            "sol": image.pixelColor(2, image.height() // 2),
            "sağ": image.pixelColor(image.width() - 3, image.height() // 2),
            "üst": image.pixelColor(image.width() // 2, 2),
            "alt": image.pixelColor(image.width() // 2, image.height() - 3),
            "sağ üst köşe": image.pixelColor(
                image.width() - 3, StatusBorderWidget.CORNER_RADIUS + 2
            ),
            "sağ alt köşe": image.pixelColor(
                image.width() - 3,
                image.height() - StatusBorderWidget.CORNER_RADIUS - 3,
            ),
        }
        for edge, pixel in samples.items():
            with self.subTest(edge=edge):
                self.assertGreater(
                    pixel.red(),
                    pixel.green(),
                    f"{edge} kenarı kırmızı değil: {pixel.getRgb()}",
                )
        widget.close()


if __name__ == "__main__":
    unittest.main()
