"""Özellik 4 — Niyet algılama test tablosu (≥10 pozitif / ≥10 negatif)."""
import unittest

from intent_detection import Intent, classify_intent, requires_atlas

# Doğru POZİTİF: somut görev/eylem → ATLAS otomatik AÇILMALI
POSITIVE_SAMPLES = [
    "atlasla ekran kartı sürücüsünü güncelle",
    "bu hatayı çöz",
    "şunu yap",
    "chrome'u aç",
    "müzik çal",
    "klavyeye merhaba yaz",
    "640, 480 tıkla",
    "önbelleği temizle",
    "servisi yeniden başlat",
    "ekran kartı sürücüsünü güncelle",
    "tarayıcıyı kapat",
    "youtube'dan müzik çal",
]

# Doğru NEGATİF: merak/bilgi sorusu → ATLAS AÇILMAMALI
NEGATIVE_SAMPLES = [
    "atlas'ı kim yaptı",
    "atlas ne demek",
    "atlas nedir",
    "atlas nasıl çalışır",
    "atlas ne işe yarar",
    "atlas güvenli mi",
    "atlas hangi dille yazılmış",
    "atlas'ın görevleri neler",
    "bugün hava nasıl",
    "yarın maç var mı",
    "python nedir",
    "atlas hakkında bilgi verir misin",  # "verir misin" istek gövdesi DEĞİL → soru/nötr
]


class IntentDetectionTests(unittest.TestCase):
    def test_positives_are_action(self):
        """≥10 pozitif örneğin tamamı ACTION sınıflandırılmalı."""
        self.assertGreaterEqual(len(POSITIVE_SAMPLES), 10)
        for sample in POSITIVE_SAMPLES:
            with self.subTest(sample=sample):
                self.assertIs(classify_intent(sample), Intent.ACTION)

    def test_negatives_are_not_action(self):
        """≥10 negatif örneğin hiçbiri ACTION olmamalı (ATLAS açılmaz)."""
        self.assertGreaterEqual(len(NEGATIVE_SAMPLES), 10)
        for sample in NEGATIVE_SAMPLES:
            with self.subTest(sample=sample):
                self.assertIsNot(classify_intent(sample), Intent.ACTION)

    def test_curiosity_questions_are_question(self):
        """Spec'teki kritik negatifler açıkça QUESTION olmalı."""
        for sample in ("atlas'ı kim yaptı", "atlas ne demek",
                       "atlas ne işe yarar", "atlas nasıl çalışır"):
            with self.subTest(sample=sample):
                self.assertIs(classify_intent(sample), Intent.QUESTION)

    def test_spec_positive_atlasla(self):
        """Spec'teki kritik pozitif: 'atlasla ekran kartı sürücüsünü güncelle'."""
        self.assertIs(
            classify_intent("atlasla ekran kartı sürücüsünü güncelle"),
            Intent.ACTION)

    def test_polite_request_is_action(self):
        """Kibar istek kalıbı ('... misin') ACTION sayılır."""
        self.assertIs(classify_intent("ekran kartını günceller misin"),
                      Intent.ACTION)

    def test_neutral_is_not_action(self):
        """Selam/teşekkür ATLAS'ı açmamalı."""
        for sample in ("merhaba", "teşekkürler", ""):
            with self.subTest(sample=sample):
                self.assertIsNot(classify_intent(sample), Intent.ACTION)

    def test_question_word_beats_domain_noun(self):
        """Soru işaretcisi, alan adı geçen sorularda kazanır."""
        self.assertIs(classify_intent("atlas güvenli mi kullanmak"),
                      Intent.QUESTION)

    def test_conversation_requests_do_not_require_atlas(self):
        """Sohbet emirleri asistan isteğidir, bilgisayar kontrolü değildir."""
        for sample in (
            "espri yap",
            "şaka yap",
            "komik bir şey söyle",
            "bana kısa bir hikaye anlat",
            "bir bilmece sor",
            "bunu açıklar mısın",
        ):
            with self.subTest(sample=sample):
                self.assertFalse(requires_atlas(sample))

    def test_explicit_computer_commands_require_atlas(self):
        for sample in (
            "Chrome'u aç",
            "youtube'dan müzik çal",
            "klavyeye merhaba yaz",
            "640, 480 tıkla",
            "ekran görüntüsü al",
            "ayarları aç",
            "Atlas'ı aç",
        ):
            with self.subTest(sample=sample):
                self.assertTrue(requires_atlas(sample))

    def test_mentions_are_not_enough_to_require_atlas(self):
        for sample in (
            "Chrome hakkında konuşalım",
            "ekran çözünürlüğü nedir",
            "müzik hakkında espri yap",
        ):
            with self.subTest(sample=sample):
                self.assertFalse(requires_atlas(sample))


if __name__ == "__main__":
    unittest.main()
