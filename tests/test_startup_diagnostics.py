import unittest
from unittest import mock

from services import startup_diagnostics


class StartupDiagnosticsTests(unittest.TestCase):
    def test_report_never_discloses_configured_api_key_values(self):
        with mock.patch.multiple(
            startup_diagnostics,
            GROQ_API_KEY="groq-secret-sentinel",
            GEMINI_API_KEY="gemini-secret-sentinel",
            OWM_API_KEY="weather-secret-sentinel",
        ), mock.patch.object(
            startup_diagnostics.importlib.util,
            "find_spec",
            return_value=object(),
        ), mock.patch.object(
            startup_diagnostics.shutil, "which", return_value="tesseract.exe"
        ):
            report = startup_diagnostics.format_startup_diagnostics()

        self.assertIn("Groq API anahtarı bulundu", report)
        self.assertIn("Gemini API anahtarı bulundu", report)
        self.assertNotIn("secret-sentinel", report)

    def test_missing_ai_provider_is_reported_as_warning(self):
        with mock.patch.multiple(
            startup_diagnostics,
            GROQ_API_KEY="",
            GEMINI_API_KEY="",
            OWM_API_KEY="",
        ), mock.patch.object(
            startup_diagnostics.importlib.util,
            "find_spec",
            return_value=None,
        ), mock.patch.object(startup_diagnostics.shutil, "which", return_value=None):
            checks = startup_diagnostics.collect_startup_diagnostics()

        self.assertEqual(checks[0][0], "UYARI")
        self.assertIn("yanıtları kullanılamayacak", checks[0][1])


if __name__ == "__main__":
    unittest.main()
