"""release.py sürüm otomasyonunun birim testleri.

Gerçek repo geçmişine/config'e dokunmaz: yollar ve git çağrıları
monkeypatch ile sahtelenir.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import release


def setUpModule() -> None:
    """Test çıktısını Windows cp1254 konsolunda güvenli kılar (→ karakterleri)."""
    release._configure_stdio()


class _FakeCompleted:
    """subprocess.CompletedProcess yerine basit sınıf."""

    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class ComputeNextVersionTests(unittest.TestCase):
    """Sürüm kademesi ve geçersizlik kontrolleri."""

    def setUp(self):
        self._orig = release._run_git
        release._run_git = lambda *a, **k: _FakeCompleted(stdout="")

    def tearDown(self):
        release._run_git = self._orig

    def test_patch_bump(self):
        self.assertEqual(
            release.compute_next_version("10.0.0", "patch", None), "10.0.1")

    def test_minor_bump(self):
        self.assertEqual(
            release.compute_next_version("10.0.3", "minor", None), "10.1.0")

    def test_major_bump(self):
        self.assertEqual(
            release.compute_next_version("9.4.2", "major", None), "10.0.0")

    def test_explicit_version_strips_v(self):
        self.assertEqual(
            release.compute_next_version("10.0.0", None, "v11.2.3"), "11.2.3")

    def test_invalid_semver_rejected(self):
        with self.assertRaises(release.ReleaseError):
            release.compute_next_version("10.0.0", None, "abc")

    def test_equal_version_rejected(self):
        with self.assertRaises(release.ReleaseError):
            release.compute_next_version("10.0.0", None, "10.0.0")

    def test_existing_tag_rejected(self):
        release._run_git = lambda *a, **k: _FakeCompleted(stdout="v10.0.1")
        with self.assertRaises(release.ReleaseError):
            release.compute_next_version("10.0.0", "patch", None)


class ConfigVersionTests(unittest.TestCase):
    """config.py okuma/güncelleme — geçici kopya üzerinde."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._orig_path = release.CONFIG_PATH
        release.CONFIG_PATH = Path(self._tmp.name) / "config.py"
        release.CONFIG_PATH.write_text(
            'APP_VERSION = "1.2.3"\nAPP_DISPLAY_VERSION = "1.2"\n',
            encoding="utf-8")

    def tearDown(self):
        release.CONFIG_PATH = self._orig_path
        self._tmp.cleanup()

    def test_read_current_version(self):
        self.assertEqual(release.read_current_version(), "1.2.3")

    def test_update_config_version(self):
        release.update_config_version("1.3.0")
        text = release.CONFIG_PATH.read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "1.3.0"', text)
        self.assertEqual(release.read_current_version(), "1.3.0")


class ChangelogTests(unittest.TestCase):
    """CHANGELOG bölüm ekleme mantığı — geçici dosya üzerinde."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._orig_path = release.CHANGELOG_PATH
        release.CHANGELOG_PATH = Path(self._tmp.name) / "CHANGELOG.md"
        release.CHANGELOG_PATH.write_text(
            "# Changelog\n\n## [10.0.0] — 2026-10-08\n\nİlk bölüm.\n",
            encoding="utf-8")

    def tearDown(self):
        release.CHANGELOG_PATH = self._orig_path
        self._tmp.cleanup()

    def test_section_prepended_before_existing(self):
        release.write_changelog("10.0.1", "Bakım sürümü.")
        text = release.CHANGELOG_PATH.read_text(encoding="utf-8")
        head10_1 = text.index("## [10.0.1]")
        head10_0 = text.index("## [10.0.0]")
        self.assertLess(head10_1, head10_0)
        self.assertIn("Bakım sürümü.", text)
        self.assertIn("İlk bölüm.", text)

    def test_default_notes_when_missing(self):
        release.write_changelog("10.0.1", None)
        text = release.CHANGELOG_PATH.read_text(encoding="utf-8")
        self.assertIn("bakım/maintenance", text)


class ReleaseErrorTests(unittest.TestCase):
    """Hata türü SystemExit türevi — süreç çıkış kodu 1 verir."""

    def test_is_system_exit(self):
        self.assertTrue(issubclass(release.ReleaseError, SystemExit))


if __name__ == "__main__":
    unittest.main()
