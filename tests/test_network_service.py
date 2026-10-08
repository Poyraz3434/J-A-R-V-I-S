import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from services import network


class NetworkResilienceTests(unittest.TestCase):
    def test_default_api_timeout_allows_slow_response_bodies(self):
        session = mock.Mock()
        session.get.return_value = _Response({"ok": True})
        url = "https://api.frankfurter.app/latest?from=slow-default-timeout"
        key = (url, (), network.DEFAULT_HTTP_TIMEOUT)
        network.REQUEST_CACHE.pop(key, None)
        with mock.patch.object(network, "HTTP_SESSION", session):
            result = network.get_cached_json(url)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            session.get.call_args.kwargs["timeout"],
            (network.HTTP_CONNECT_TIMEOUT_SECONDS, network.HTTP_READ_TIMEOUT_SECONDS),
        )

    def test_shared_session_retries_only_idempotent_read_requests(self):
        adapter = network.HTTP_SESSION.get_adapter("https://")
        retry = adapter.max_retries

        self.assertEqual(retry.total, network.HTTP_RETRY_TOTAL)
        self.assertEqual(retry.read, network.HTTP_RETRY_TOTAL)
        self.assertIn("GET", retry.allowed_methods)
        self.assertIn("HEAD", retry.allowed_methods)
        self.assertNotIn("POST", retry.allowed_methods)
        self.assertTrue(retry.respect_retry_after_header)

    def test_temporary_network_failure_returns_controlled_empty_result(self):
        session = mock.Mock()
        session.get.side_effect = network.requests.exceptions.Timeout("slow link")
        url = "https://api.frankfurter.app/latest?from=timeout-test"
        with mock.patch.object(network, "HTTP_SESSION", session), mock.patch.object(
            network.logger, "warning"
        ) as warning:
            result = network.get_cached_json(url, timeout=1, cache_ttl=0)

        self.assertIsNone(result)
        warning.assert_called_once()


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class CachedJsonTests(unittest.TestCase):
    def setUp(self):
        self.session = mock.Mock()
        self.session.get.return_value = _Response({"value": 1})
        self.session_patch = mock.patch.object(network, "HTTP_SESSION", self.session)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()

    def test_reuses_fresh_cache_entry(self):
        url = "https://api.frankfurter.app/latest?from=cache-test"
        network.REQUEST_CACHE.pop((url, (), 2), None)

        first = network.get_cached_json(url, timeout=2)
        second = network.get_cached_json(url, timeout=2)

        self.assertEqual(first, {"value": 1})
        self.assertEqual(second, first)
        self.session.get.assert_called_once()

    def test_stale_fallback_has_a_finite_age_limit(self):
        url = "https://api.frankfurter.app/latest?from=stale-test"
        key = (url, (), 2)
        network.REQUEST_CACHE.pop(key, None)
        clock = [100.0]
        time_patch = mock.patch.object(network.time, "time", side_effect=lambda: clock[0])
        time_patch.start()
        self.addCleanup(time_patch.stop)

        self.assertEqual(
            network.get_cached_json(url, timeout=2, cache_ttl=1, stale_ttl=5),
            {"value": 1},
        )
        self.session.get.side_effect = OSError("offline")
        clock[0] = 104.0
        self.assertEqual(
            network.get_cached_json(url, timeout=2, cache_ttl=1, stale_ttl=5),
            {"value": 1},
        )
        clock[0] = 107.0
        self.assertIsNone(
            network.get_cached_json(url, timeout=2, cache_ttl=1, stale_ttl=5)
        )

    def test_concurrent_miss_for_same_url_uses_one_request(self):
        url = "https://api.frankfurter.app/latest?from=singleflight-test"
        key = (url, (), 2)
        network.REQUEST_CACHE.pop(key, None)
        entered = threading.Event()

        def delayed_get(*args, **kwargs):
            entered.set()
            time.sleep(0.05)
            return _Response({"value": 2})

        self.session.get.side_effect = delayed_get
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(
                lambda _: network.get_cached_json(url, timeout=2),
                range(4),
            ))

        self.assertEqual(results, [{"value": 2}] * 4)
        self.assertTrue(entered.is_set())
        self.session.get.assert_called_once()
        self.assertNotIn(key, network.REQUEST_CACHE_KEY_LOCKS)

    def test_rejects_hosts_outside_the_allowlist(self):
        self.assertIsNone(
            network.get_cached_json("https://example.com/latest", timeout=2)
        )
        self.session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
