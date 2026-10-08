"""Özellik 8 — Müfredat + 3 sn doğrulama testleri."""
import unittest

import curriculum as cur


class CurriculumDataTests(unittest.TestCase):
    def test_all_twelve_grades_loaded(self):
        data = cur.load_curriculum()
        grades = data["grades"]
        self.assertEqual(sorted(grades, key=int),
                         [str(i) for i in range(1, 13)])

    def test_grade9_has_high_school_subjects(self):
        subjects = cur.load_curriculum()["grades"]["9"]
        for s in ("Matematik", "Fizik", "Kimya", "Biyoloji"):
            self.assertIn(s, subjects)
            self.assertTrue(subjects[s])

    def test_estimate_grade(self):
        self.assertEqual(cur.estimate_grade("3. sınıf matematik sorusu"), 3)
        self.assertEqual(cur.estimate_grade("Lise fizik ödevi"), 9)
        self.assertIsNone(cur.estimate_grade("hava nasıl"))

    def test_subject_and_education_detection(self):
        self.assertEqual(cur.subject_of("kesirler nasıl hesaplanır"), "Matematik")
        self.assertEqual(cur.subject_of("fizik test çöz"), "Fizik")
        self.assertTrue(cur.is_education_query("5. sınıfa kesirler nedir"))
        self.assertTrue(cur.is_education_query("fizik ödevimi çöz"))
        self.assertFalse(cur.is_education_query("atlas ne işe yarar"))
        self.assertFalse(cur.is_education_query("merhaba"))

    def test_context_has_level_language_instruction(self):
        ctx = cur.curriculum_context(3, "Matematik")
        self.assertIn("3. sınıf", ctx)
        self.assertIn("Matematik", ctx)
        self.assertIn("YANIT DİLİ", ctx)
        unknown = cur.curriculum_context(None)
        self.assertIn("belirtilmemiş", unknown)


class VerifyAnswerTests(unittest.TestCase):
    def test_full_three_second_requirement(self):
        """Spec: cevap sunumundan önce TAM 3 saniyelik doğrulama süresi."""
        vr = cur.verify_answer("q", "a", llm_fn=None)   # LLM yok → hızlı ama 3 sn bekler
        self.assertGreaterEqual(vr.elapsed, 3.0)
        self.assertEqual(vr.verdict, "şüpheli")

    def test_llm_json_parsed(self):
        fake = lambda q, i, c: '{"verdict": "dogru", "confidence": 0.92, "reason": "doğru"}'
        vr = cur.verify_answer("q", "a", llm_fn=fake, min_seconds=0.05)
        self.assertEqual(vr.verdict, "doğru")
        self.assertAlmostEqual(vr.confidence, 0.92, places=2)

    def test_malformed_llm_output_is_suspicious(self):
        vr = cur.verify_answer("q", "a", llm_fn=lambda *a: "bozuk metin",
                               min_seconds=0.05)
        self.assertEqual(vr.verdict, "şüpheli")
        self.assertEqual(vr.confidence, 0.0)

    def test_llm_exception_is_caught(self):
        def boom(*a):
            raise RuntimeError("ağ hatası")
        vr = cur.verify_answer("q", "a", llm_fn=boom, min_seconds=0.05)
        self.assertEqual(vr.verdict, "şüpheli")
        self.assertIn("Hata", vr.reason)


if __name__ == "__main__":
    unittest.main()
