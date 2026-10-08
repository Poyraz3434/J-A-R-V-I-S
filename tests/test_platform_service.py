"""Özellik 2 — PlatformService testleri (tek codebase, runtime tespit)."""
import unittest
from unittest import mock

import platform_service as ps


class FactoryTests(unittest.TestCase):
    def setUp(self):
        ps._service_instance = None

    def tearDown(self):
        ps._service_instance = None

    def test_windows_factory(self):
        with mock.patch.object(ps.platform, "system", return_value="Windows"):
            svc = ps.get_platform_service()
        self.assertIsInstance(svc, ps.WindowsPlatformService)
        self.assertEqual(svc.name, "windows")

    def test_macos_factory(self):
        with mock.patch.object(ps.platform, "system", return_value="Darwin"):
            ps._service_instance = None
            svc = ps.get_platform_service()
        self.assertIsInstance(svc, ps.MacPlatformService)
        self.assertEqual(svc.name, "macos")

    def test_singleton_same_instance(self):
        a = ps.get_platform_service()
        b = ps.get_platform_service()
        self.assertIs(a, b)


class MacServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = ps.MacPlatformService()

    def test_permissions_guide_lists_accessibility_and_screen(self):
        perms = self.svc.permissions_needed()
        self.assertEqual(len(perms), 2)
        titles = " ".join(p["title"] for p in perms)
        self.assertIn("Accessibility", titles)
        self.assertIn("Ekran Kaydı", titles)
        for p in perms:   # her izin için neden + nasıl + ayar URL'si
            self.assertTrue(p["why"] and p["how"] and p["settings_url"])

    def test_open_settings_message(self):
        msg = self.svc.open_settings("accessibility")
        self.assertIn("Sistem Ayarları", msg)

    def test_auto_start_off_is_safe(self):
        msg = self.svc.set_auto_start(False)
        self.assertIn("kapatıldı", msg)


class WindowsServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = ps.WindowsPlatformService()

    def test_no_extra_permissions_needed(self):
        self.assertEqual(self.svc.permissions_needed(), [])
        self.assertIn("Windows", self.svc.accessibility_status())

    def test_auto_start_off_is_safe(self):
        msg = self.svc.set_auto_start(False)
        self.assertIn("kapatıldı", msg)

    def test_auto_start_enabled_reflects_shortcut(self):
        """Devre dışı bıraktıktan sonra durum False (kısayol yok/temizlendi)."""
        self.svc.set_auto_start(False)
        self.assertFalse(self.svc.auto_start_enabled())
        self.assertIsInstance(self.svc.auto_start_enabled(), bool)

    def test_show_file_missing_path(self):
        msg = self.svc.show_file("yok/olmayan/dosya.txt")
        self.assertIn("bulunamadı", msg)


class GuideGuardTests(unittest.TestCase):
    def setUp(self):
        ps._service_instance = None

    def tearDown(self):
        ps._service_instance = None

    def test_guide_skipped_on_windows(self):
        """Windows'ta izin rehberi DİYALOĞU açılmamalı (hızlı/False)."""
        with mock.patch.object(ps.platform, "system", return_value="Windows"):
            ps._service_instance = None
            shown = ps.maybe_show_permissions_guide(settings={})
        self.assertFalse(shown)

    def test_guide_shown_only_once_on_mac(self):
        """macOS'ta ikinci kez gösterilmez (bayrak korunur)."""
        with mock.patch.object(ps, "get_platform_service",
                               return_value=ps.MacPlatformService()):
            with mock.patch.object(ps, "maybe_show_permissions_guide",
                                   side_effect=ps.maybe_show_permissions_guide):
                settings = {"macos_guide_shown": True}
                self.assertFalse(ps.maybe_show_permissions_guide(
                    settings=settings))


if __name__ == "__main__":
    unittest.main()
