"""Özellik 9 — Prompt Mimarı testleri (tetikleme + 8 maddelik checklist)."""
import unittest

from prompt_architect import (
    build_fallback_prompt,
    checklist_quality,
    generate_prompt,
    is_prompt_request,
)

ALL_KEYS = ("role", "task", "constraints", "assumptions", "edge",
            "output", "example", "criteria")


class TriggerTests(unittest.TestCase):
    def test_positive_triggers(self):
        for sample in ("şu iş için bana detaylı bir prompt yaz",
                       "web sitesi için prompt oluştur",
                       "e-posta için prompt hazırla",
                       "prompt moduna geç"):
            with self.subTest(sample=sample):
                self.assertTrue(is_prompt_request(sample), sample)

    def test_negative_info_questions(self):
        """Bilgi soruları TETİKLENMEZ (normal cevap verilir)."""
        for sample in ("prompt nedir", "prompt ne demek",
                       "prompt nasıl çalışır", "merhaba"):
            with self.subTest(sample=sample):
                self.assertFalse(is_prompt_request(sample), sample)


class ChecklistTests(unittest.TestCase):
    def test_fallback_contains_all_eight_sections(self):
        text = build_fallback_prompt("X işi için prompt")
        report = checklist_quality(text)
        for key in ALL_KEYS:
            self.assertTrue(report[key], f"eksik bölüm: {key}")
        self.assertTrue(all(report.values()))

    def test_quality_detects_missing_sections(self):
        report = checklist_quality("Sadece rastgele bir cevap metni.")
        self.assertFalse(any(report.values()))

    def test_generate_completes_missing_sections(self):
        """LLM eksik bölüm döndürürse şablondan tamamlanır (self-check)."""
        def partial_llm(task, instruction, context):
            return "## ROL\nSen bir asistansın.\n## GÖREV\nAdım adım yap."
        text, report = generate_prompt("görev", llm_fn=partial_llm)
        self.assertTrue(all(report.values()),
                        f"tamamlama sonrası eksik: {report}")

    def test_generate_without_llm_uses_fallback(self):
        text, report = generate_prompt("görev", llm_fn=None)
        self.assertTrue(all(report.values()))
        self.assertIn("GÖREV", text)

    def test_llm_exception_falls_back(self):
        def boom(*a):
            raise RuntimeError("hata")
        text, report = generate_prompt("görev", llm_fn=boom)
        self.assertTrue(all(report.values()))


if __name__ == "__main__":
    unittest.main()
