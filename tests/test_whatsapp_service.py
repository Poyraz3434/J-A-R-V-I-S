import os
import unittest
from unittest import mock

from services import whatsapp


class WhatsAppServiceTests(unittest.TestCase):
    def test_unconfigured_message_fails_without_network(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("urllib.request.urlopen") as urlopen:
                result = whatsapp.send_message("+905551112233", "selam")
        self.assertFalse(result["ok"])
        urlopen.assert_not_called()

    def test_callmebot_success_is_normalized(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b"Message queued"
        response.__enter__.return_value = response
        with mock.patch.dict(
            os.environ,
            {"JARVIS_WA_PHONE": "+905551112233", "JARVIS_WA_APIKEY": "key"},
            clear=True,
        ):
            with mock.patch("urllib.request.urlopen", return_value=response):
                result = whatsapp.send_message("+905551112233", "selam")
        self.assertEqual(result["provider"], "callmebot")
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
