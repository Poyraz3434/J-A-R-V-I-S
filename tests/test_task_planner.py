import unittest

from services.task_planner import build_task_plan, format_task_plan


class TaskPlannerTests(unittest.TestCase):
    def test_chained_request_creates_ordered_plan(self):
        plan = build_task_plan("Chrome'u aç sonra Google'da hava durumunu ara")
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 2)
        self.assertIn("Chrome'u aç", plan.steps[0].request)
        self.assertIn("Google'da", plan.steps[1].request)

    def test_explicit_plan_prefix_accepts_single_step(self):
        plan = build_task_plan("Planla: masaüstündeki dosyaları göster")
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 1)

    def test_risky_steps_are_marked(self):
        plan = build_task_plan("Planla: dosya sil")
        self.assertIsNotNone(plan)
        self.assertIn("Yüksek", plan.steps[0].risk)
        self.assertIn("henüz hiçbir adım çalıştırılmadı", format_task_plan(plan))

    def test_normal_single_request_is_not_intercepted(self):
        self.assertIsNone(build_task_plan("Bana bir espri yap"))

    def test_plan_size_is_bounded(self):
        request = "Planla: a sonra b sonra c sonra d sonra e"
        self.assertIsNone(build_task_plan(request))


if __name__ == "__main__":
    unittest.main()
