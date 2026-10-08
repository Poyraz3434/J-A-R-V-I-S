import unittest

from services.ai_intent import AIRequestType, classify_ai_request


class AIIntentRoutingTests(unittest.TestCase):
    def test_small_talk_uses_fast_chat_route(self):
        for text in (
            "Selam",
            "Naber?",
            "Nasılsın?",
            "Bugün nasılsın?",
            "Bana kısa bir hikaye anlat",
            "Bana bir fıkra anlat",
            "Espri yap",
        ):
            with self.subTest(text=text):
                self.assertIs(classify_ai_request(text), AIRequestType.CHAT)

    def test_fact_questions_use_knowledge_route(self):
        for text in (
            "Türkiye'nin başkenti neresidir?",
            "Yerçekimi nasıl çalışır?",
            "Fotosentez nedir?",
            "Bana makine öğrenmesi hakkında bilgi ver",
        ):
            with self.subTest(text=text):
                self.assertIs(
                    classify_ai_request(text),
                    AIRequestType.KNOWLEDGE,
                )

    def test_current_and_explicit_web_queries_use_search_route(self):
        for text in (
            "Bugünkü son dakika haberleri neler?",
            "Gemini API'nin güncel fiyatını internetten ara",
            "Bugün dolar kuru ne kadar?",
            "Bu hafta çıkan teknoloji haberleri",
        ):
            with self.subTest(text=text):
                self.assertIs(
                    classify_ai_request(text),
                    AIRequestType.WEB_SEARCH,
                )

    def test_routing_regression_examples_cover_turkish_variants(self):
        examples = (
            ("Selam, nasılsın?", AIRequestType.CHAT),
            ("Sağ ol, çok yardımcı oldun", AIRequestType.CHAT),
            ("Python'da liste nasıl sıralanır?", AIRequestType.KNOWLEDGE),
            ("Fotosentez ne demek?", AIRequestType.KNOWLEDGE),
            ("Kuantum bilgisayarları kısaca açıkla", AIRequestType.KNOWLEDGE),
            ("Bugün İstanbul'da hava nasıl?", AIRequestType.WEB_SEARCH),
            ("Dolar kurunu internetten kontrol et", AIRequestType.WEB_SEARCH),
            ("En son Gemini sürümünü bul", AIRequestType.WEB_SEARCH),
        )
        for text, expected_route in examples:
            with self.subTest(text=text):
                self.assertIs(classify_ai_request(text), expected_route)


if __name__ == "__main__":
    unittest.main()
