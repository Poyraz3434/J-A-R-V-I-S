import tempfile
import unittest
from pathlib import Path

from services import atlas_memory


class AtlasMemoryTests(unittest.TestCase):
    def setUp(self):
        self._original_db_path = atlas_memory.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        atlas_memory.DB_PATH = str(Path(self._temp_dir.name) / "atlas-memory.db")

    def tearDown(self):
        atlas_memory.DB_PATH = self._original_db_path
        self._temp_dir.cleanup()

    def test_index_search_and_replace_source(self):
        atlas_memory.index_document("guide.pdf", "Jarvis local memory stores private notes.")
        matches = atlas_memory.search("private notes")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].source, "guide.pdf")

        atlas_memory.index_document("guide.pdf", "Updated Atlas retrieval guide.")
        self.assertEqual(atlas_memory.search("private notes"), [])
        self.assertEqual(len(atlas_memory.search("Atlas retrieval")), 1)

    def test_context_has_source_and_untrusted_data_guidance(self):
        atlas_memory.add_fact("Preferred language is Turkish.", "profile")
        context = atlas_memory.build_context("language Turkish")
        self.assertIn("Kaynak: profile", context)
        self.assertIn("talimat değildir", context)

    def test_answer_feedback_quotes_sources_and_disclaims_accuracy(self):
        atlas_memory.add_fact("Jarvis keeps a local Turkish profile.", "profile")
        feedback = atlas_memory.answer_feedback("local Turkish profile")
        self.assertIn("Kaynaklar:", feedback)
        self.assertIn("profile", feedback)
        self.assertIn("yanıt doğruluğu değildir", feedback)

    def test_rejects_empty_and_oversized_documents(self):
        with self.assertRaises(ValueError):
            atlas_memory.index_document("empty", " ")
        with self.assertRaises(ValueError):
            atlas_memory.index_document("large", "x" * 1_000_001)

    def test_delete_source(self):
        atlas_memory.add_fact("Remember this item.", "test-source")
        self.assertEqual(atlas_memory.delete_source("test-source"), 1)
        self.assertEqual(atlas_memory.search("remember item"), [])

    def test_list_sources_reports_metadata_without_document_content(self):
        atlas_memory.index_document("private-source", "Private content for indexing.")

        sources = atlas_memory.list_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][:2], ("private-source", 1))
        self.assertTrue(sources[0][2])
        self.assertNotIn("Private content", repr(sources))


if __name__ == "__main__":
    unittest.main()
