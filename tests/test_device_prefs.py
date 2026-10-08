"""Özellik 4 — IP/makine bazlı tercih saklama testleri."""
import unittest

import device_prefs


class DevicePrefsTests(unittest.TestCase):
    def setUp(self):
        self.settings = {}
        self._orig_ip = device_prefs.get_local_ip

    def tearDown(self):
        device_prefs.get_local_ip = self._orig_ip  # geri al

    @staticmethod
    def _set_ip(ip: str) -> None:
        device_prefs.get_local_ip = lambda: ip

    def test_save_and_load_same_ip(self):
        """Aynı IP ile kaydet/oku → değer geri gelir (birincil anahtar)."""
        self._set_ip("192.168.1.10")
        device_prefs.save_device_pref(self.settings, "atlas_auto_open", False)
        self.assertIs(
            device_prefs.load_device_pref(self.settings, "atlas_auto_open", True),
            False)

    def test_machine_fallback_when_ip_changes(self):
        """IP değişirse (dinamik IP) makine kimliği yedeği devreye girer."""
        self._set_ip("192.168.1.10")
        device_prefs.save_device_pref(self.settings, "atlas_auto_open", False)
        self._set_ip("10.0.0.5")  # ağ değişti
        self.assertIs(
            device_prefs.load_device_pref(self.settings, "atlas_auto_open", True),
            False)

    def test_default_when_nothing_saved(self):
        """Hiç kayıt yoksa default döner."""
        self._set_ip("192.168.1.10")
        self.assertIs(
            device_prefs.load_device_pref(self.settings, "atlas_auto_open", True),
            True)
        self.assertIsNone(device_prefs.load_device_pref(self.settings, "missing"))

    def test_writes_both_ip_and_machine_keys(self):
        """Kayıt hem IP hem machine: alt anahtarlarını yazmalı."""
        self._set_ip("192.168.1.10")
        device_prefs.save_device_pref(self.settings, "atlas_auto_open", True)
        keys = self.settings["device_prefs"].keys()
        self.assertIn("192.168.1.10", keys)
        mid = device_prefs.get_machine_id()
        self.assertIn(f"machine:{mid}", keys)

    def test_machine_id_is_stable_and_nonempty(self):
        """Makine kimliği sabit ve boş olmamalı."""
        a = device_prefs.get_machine_id()
        b = device_prefs.get_machine_id()
        self.assertEqual(a, b)
        self.assertTrue(a)
        self.assertLessEqual(len(a), 64)

    def test_unknown_key_returns_default(self):
        self._set_ip("192.168.1.10")
        device_prefs.save_device_pref(self.settings, "atlas_auto_open", False)
        self.assertEqual(
            device_prefs.load_device_pref(self.settings, "other_key", "d"),
            "d")


if __name__ == "__main__":
    unittest.main()
