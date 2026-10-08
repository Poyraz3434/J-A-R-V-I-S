import unittest

from benchmarks.benchmark_pipeline import benchmark_callable


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_callable_benchmark_reports_latency_and_memory_metrics(self):
        report = benchmark_callable(lambda: sum(range(10)), number=2, repeats=2)

        self.assertEqual(report["runs_per_sample"], 2.0)
        self.assertEqual(report["samples"], 2.0)
        self.assertGreaterEqual(report["average_ms"], 0)
        self.assertGreaterEqual(report["median_ms"], 0)
        self.assertGreaterEqual(report["p95_sample_ms"], 0)
        self.assertGreaterEqual(report["python_peak_allocated_kib"], 0)

    def test_callable_benchmark_rejects_zero_samples(self):
        with self.assertRaises(ValueError):
            benchmark_callable(lambda: None, number=0)


if __name__ == "__main__":
    unittest.main()
