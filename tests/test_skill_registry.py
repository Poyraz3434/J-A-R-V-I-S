import unittest

from services.skill_registry import (
    SkillDefinition,
    SkillRegistry,
    create_builtin_skill_registry,
)


class SkillRegistryTests(unittest.TestCase):
    def test_builtin_catalog_describes_existing_capability_groups(self):
        registry = create_builtin_skill_registry()
        skill_ids = {skill.skill_id for skill in registry.all()}

        self.assertTrue({
            "research", "presentation", "file_conversion", "computer_control",
            "local_memory", "backup_restore", "diagnostics",
        }.issubset(skill_ids))
        self.assertTrue(registry.get("file_mutation").confirmation_required)

    def test_register_rejects_duplicate_and_empty_ids(self):
        registry = SkillRegistry()
        skill = SkillDefinition("test", "Test", "Test skill")
        registry.register(skill)

        with self.assertRaisesRegex(ValueError, "zaten kayıtlı"):
            registry.register(skill)
        with self.assertRaisesRegex(ValueError, "boş olamaz"):
            registry.register(SkillDefinition("", "Missing", "No id"))

    def test_dispatch_calls_only_the_named_handler(self):
        received = []
        registry = SkillRegistry()
        registry.register(SkillDefinition(
            "test", "Test", "Test skill",
            handler=lambda query: received.append(query) or "done",
        ))

        self.assertEqual(registry.dispatch("test", "run"), "done")
        self.assertEqual(received, ["run"])

    def test_matching_is_case_insensitive_and_metadata_only_skills_are_not_run(self):
        registry = create_builtin_skill_registry()

        self.assertEqual(
            [skill.skill_id for skill in registry.match("Sunum Hazırla")],
            ["presentation"],
        )
        self.assertIsNone(registry.dispatch("presentation", "sunum hazırla"))


if __name__ == "__main__":
    unittest.main()
