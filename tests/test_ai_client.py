import sys
import types
import unittest
from unittest import mock

from services.ai_client import (
    AI_MAX_RETRIES,
    AI_REQUEST_TIMEOUT_SECONDS,
    GEMINI_BASE_URL,
    GROQ_MAX_RETRIES,
    GROQ_REQUEST_TIMEOUT_SECONDS,
    create_gemini_client,
    create_groq_client,
    gemini_grounded_search,
)


class GroqClientDefaultsTests(unittest.TestCase):
    def test_factory_applies_bounded_timeout_and_disables_retries(self):
        groq_module = types.SimpleNamespace(Groq=mock.Mock(return_value="client"))
        with mock.patch.dict(sys.modules, {"groq": groq_module}):
            client = create_groq_client("test-key")

        self.assertEqual(client, "client")
        groq_module.Groq.assert_called_once_with(
            api_key="test-key",
            timeout=GROQ_REQUEST_TIMEOUT_SECONDS,
            max_retries=GROQ_MAX_RETRIES,
        )

    def test_factory_rejects_missing_api_key(self):
        with mock.patch.dict(
            "os.environ",
            {"JARVIS_GROQ_API_KEY": "", "GROQ_API_KEY": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "API anahtarı"):
                create_groq_client("")

    def test_gemini_factory_uses_openai_compatible_google_endpoint(self):
        openai_module = types.SimpleNamespace(OpenAI=mock.Mock(return_value="gemini"))
        with mock.patch.dict(sys.modules, {"openai": openai_module}):
            client = create_gemini_client("test-gemini-key")

        self.assertEqual(client, "gemini")
        openai_module.OpenAI.assert_called_once_with(
            api_key="test-gemini-key",
            base_url=GEMINI_BASE_URL,
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=AI_MAX_RETRIES,
        )

    def test_gemini_factory_rejects_missing_api_key(self):
        with mock.patch.dict(
            "os.environ",
            {"JARVIS_GEMINI_API_KEY": "", "GEMINI_API_KEY": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "Gemini API anahtarı"):
                create_gemini_client("")

    def test_grounded_search_posts_search_tool_and_returns_citations(self):
        response = mock.Mock()
        response.json.return_value = {
            "output_text": "Bulunan yanıt.",
            "steps": [{
                "type": "model_output",
                "content": [{
                    "type": "text",
                    "text": "Bulunan yanıt.",
                    "annotations": [{
                        "type": "url_citation",
                        "title": "Örnek Kaynak",
                        "url": "https://example.com/article",
                    }],
                }],
            }],
        }
        with mock.patch("requests.post", return_value=response) as post:
            result = gemini_grounded_search(
                "Güncel bilgi?", "gemini-test", api_key="test-key"
            )

        self.assertIn("Bulunan yanıt.", result)
        self.assertIn("https://example.com/article", result)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(
            args[0],
            "https://generativelanguage.googleapis.com/v1beta/interactions",
        )
        self.assertEqual(kwargs["headers"], {"x-goog-api-key": "test-key"})
        self.assertEqual(kwargs["json"]["tools"], [{"type": "google_search"}])
        response.close.assert_called_once()

    def test_grounded_search_skips_body_read_if_cancelled_after_headers(self):
        response = mock.Mock()
        cancel_event = mock.Mock()
        cancel_event.is_set.return_value = True
        registered = []

        with mock.patch("requests.post", return_value=response):
            result = gemini_grounded_search(
                "query",
                "model",
                api_key="test-key",
                cancel_event=cancel_event,
                response_callback=registered.append,
            )

        self.assertEqual(result, "")
        response.json.assert_not_called()
        response.close.assert_called_once()
        self.assertEqual(registered, [response, None])


if __name__ == "__main__":
    unittest.main()
