"""Özellik 6 — WindowManager birim testleri (karşılıklı dışlayıcı davranış)."""
import unittest

from window_manager import ActiveWindow, WindowManager


class FakeWindow:
    """Gerçek Qt penceresi yerine kullanılan sahte pencere (kayıt defteri tutar)."""

    def __init__(self, name: str):
        self.name = name
        self.visible = False
        self.calls: list[str] = []

    def show(self):
        self.visible = True
        self.calls.append("show")

    def hide(self):
        self.visible = False
        self.calls.append("hide")

    def raise_(self):
        self.calls.append("raise_")

    def activateWindow(self):
        self.calls.append("activateWindow")


class WindowManagerTests(unittest.TestCase):
    def setUp(self):
        self.jarvis = FakeWindow("jarvis")
        self.atlas = FakeWindow("atlas")
        self.manager = WindowManager(animate=False)
        self.manager.register(ActiveWindow.JARVIS, self.jarvis)
        self.manager.register(ActiveWindow.ATLAS, self.atlas)
        self.events: list[str] = []
        self.manager.active_changed.connect(self.events.append)

    def test_open_atlas_hides_jarvis(self):
        """ATLAS açılınca JARVIS gizlenmeli; sadece ATLAS görünür kalmalı."""
        self.jarvis.show()
        self.manager.open_atlas()
        self.assertFalse(self.jarvis.visible)
        self.assertTrue(self.atlas.visible)
        self.assertIs(self.manager.active, ActiveWindow.ATLAS)
        self.assertEqual(self.events, [ActiveWindow.ATLAS.value])

    def test_open_jarvis_restores_jarvis(self):
        """ATLAS kapanınca JARVIS geri açılmalı; ikisi birden açık kalmamalı."""
        self.jarvis.show()
        self.manager.open_atlas()
        self.manager.open_jarvis()
        self.assertTrue(self.jarvis.visible)
        self.assertFalse(self.atlas.visible)
        self.assertIs(self.manager.active, ActiveWindow.JARVIS)
        self.assertEqual(self.events, [ActiveWindow.ATLAS.value, ActiveWindow.JARVIS.value])

    def test_manual_open_blocked_while_atlas_active(self):
        """ATLAS aktifken manuel 'JARVIS'i aç' reddedilmeli; ATLAS öne alınır."""
        self.jarvis.show()
        self.manager.open_atlas()
        self.assertFalse(self.manager.request_jarvis())
        self.assertFalse(self.jarvis.visible)
        self.assertTrue(self.atlas.visible)
        self.assertIn("raise_", self.atlas.calls)

    def test_manual_open_allowed_while_atlas_closed(self):
        """ATLAS kapalıyken tepsi 'Aç' isteği JARVIS'i açabilmeli."""
        self.assertTrue(self.manager.request_jarvis())
        self.assertIs(self.manager.active, ActiveWindow.JARVIS)
        self.assertTrue(self.jarvis.visible)

    def test_no_signal_duplicate_on_same_target(self):
        """Aynı pencereye tekrar geçişte active_changed tekrarlanmamalı."""
        self.manager.open_jarvis()  # zaten JARVIS aktif
        self.assertEqual(self.events, [])

    def test_unregistered_window_is_ignored(self):
        """Kaydı olmayan hedefte geçiş sessizce iptal edilmeli."""
        self.jarvis.show()
        manager = WindowManager(animate=False)
        manager.register(ActiveWindow.JARVIS, self.jarvis)
        manager.open_atlas()  # ATLAS kayıtlı değil
        self.assertIs(manager.active, ActiveWindow.JARVIS)
        self.assertTrue(self.jarvis.visible)
        self.assertFalse(self.atlas.visible)

    def test_windows_never_both_visible(self):
        """Her geçişten sonra tam olarak tek pencere görünür olmalı."""
        steps = (
            self.manager.open_atlas,
            self.manager.open_jarvis,
            self.manager.open_atlas,
            self.manager.open_jarvis,
        )
        for step in steps:
            step()
            self.assertNotEqual(
                self.jarvis.visible, self.atlas.visible,
                "Pencerelerden hiçbiri/ikisi birden görünür — dışlayıcı bozuldu.",
            )

    def test_hiding_is_used_not_close(self):
        """Geçişte hide çağrısı yapılır (bağlam korunur); close asla çağrılmaz."""
        self.jarvis.show()
        self.manager.open_atlas()
        self.assertIn("hide", self.jarvis.calls)
        self.assertNotIn("close", self.jarvis.calls)


if __name__ == "__main__":
    unittest.main()