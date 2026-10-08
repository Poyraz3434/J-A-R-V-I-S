import unittest

from services.task_center import StepStatus, TaskCenter, TaskStatus


class TaskCenterTests(unittest.TestCase):
    def test_tracks_task_steps_and_returns_isolated_snapshots(self):
        center = TaskCenter()
        task_id = center.create(
            "Research workflow",
            [("Search", "research"), ("Write report", "presentation")],
        )
        center.start(task_id, "Starting")
        center.update_step(task_id, 0, StepStatus.RUNNING)
        center.update_step(task_id, 0, StepStatus.SUCCEEDED)
        center.update_step(task_id, 1, StepStatus.RUNNING, "Generating")

        snapshot = center.snapshot()[0]
        self.assertEqual(snapshot.status, TaskStatus.RUNNING)
        self.assertEqual(snapshot.steps[0].status, StepStatus.SUCCEEDED)
        self.assertEqual(snapshot.steps[1].message, "Generating")
        snapshot.steps.clear()
        self.assertEqual(len(center.snapshot()[0].steps), 2)

    def test_cancel_invokes_callback_and_records_cancelling_state(self):
        calls = []
        center = TaskCenter()
        task_id = center.create("Long task", cancel_callback=lambda: calls.append(True))
        center.start(task_id)

        self.assertTrue(center.request_cancel(task_id))
        self.assertEqual(calls, [True])
        self.assertEqual(center.snapshot()[0].status, TaskStatus.CANCELLING)

    def test_cancel_without_callback_finishes_immediately(self):
        center = TaskCenter()
        task_id = center.create("Queued task")

        self.assertTrue(center.request_cancel(task_id))
        self.assertEqual(center.snapshot()[0].status, TaskStatus.CANCELLED)

    def test_failed_cancel_callback_restores_running_state(self):
        def fail_cancel():
            raise RuntimeError("unsafe")

        center = TaskCenter()
        task_id = center.create(
            "Task that cannot stop",
            cancel_callback=fail_cancel,
        )
        center.start(task_id)

        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            center.request_cancel(task_id)
        self.assertEqual(center.snapshot()[0].status, TaskStatus.RUNNING)
        self.assertEqual(center.snapshot()[0].message, "İptal başlatılamadı.")

    def test_history_is_bounded_and_terminal_states_are_validated(self):
        center = TaskCenter(history_limit=2)
        first = center.create("first")
        center.create("second")
        center.create("third")

        self.assertEqual(len(center.snapshot()), 2)
        with self.assertRaises(KeyError):
            center.finish(first, TaskStatus.SUCCEEDED)
        with self.assertRaises(ValueError):
            center.finish(center.snapshot()[0].task_id, TaskStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
