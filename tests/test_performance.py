import unittest

from services.performance import detect_low_resource_mode


class LowResourceDetectionTests(unittest.TestCase):
    def test_detects_first_generation_i3_class_hardware(self):
        self.assertTrue(detect_low_resource_mode(4, 8 * 1024**3))
        self.assertTrue(detect_low_resource_mode(8, 4 * 1024**3))

    def test_keeps_more_capable_hardware_in_normal_mode(self):
        self.assertFalse(detect_low_resource_mode(8, 8 * 1024**3))

    def test_unknown_hardware_values_do_not_force_low_resource_mode(self):
        self.assertFalse(detect_low_resource_mode(None, None))
        self.assertFalse(detect_low_resource_mode(0, 0))


if __name__ == "__main__":
    unittest.main()
