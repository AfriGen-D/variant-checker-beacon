"""
Unit tests for QueryRateThrottle.

Standalone like test_middleware: no MongoDB, minimal settings.

    python -m beacon_api.test_query_throttle
"""
import unittest

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-only',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        BEACON_RATE_LIMITS={},
        REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'anon': '100/hour'}},
    )
    import django

    django.setup()

from django.test import override_settings  # noqa: E402

from beacon_api.views_boolean import QueryRateThrottle  # noqa: E402


class QueryRateThrottleTests(unittest.TestCase):
    def test_default_is_fifty_an_hour(self):
        with override_settings(BEACON_RATE_LIMITS={}):
            self.assertEqual(QueryRateThrottle().rate, '50/hour')
            self.assertEqual(QueryRateThrottle().num_requests, 50)

    def test_follows_the_query_endpoint_setting(self):
        with override_settings(BEACON_RATE_LIMITS={'query': '1000000/hour'}):
            throttle = QueryRateThrottle()
            self.assertEqual(throttle.rate, '1000000/hour')
            self.assertEqual(throttle.num_requests, 1000000)
            self.assertEqual(throttle.duration, 3600)

    def test_an_empty_setting_keeps_the_default(self):
        with override_settings(BEACON_RATE_LIMITS={'query': ''}):
            self.assertEqual(QueryRateThrottle().rate, '50/hour')

    def test_a_missing_setting_object_keeps_the_default(self):
        with override_settings():
            del settings.BEACON_RATE_LIMITS
            self.assertEqual(QueryRateThrottle().rate, '50/hour')


class QueryThrottleIsolationTests(unittest.TestCase):
    """Review G2: the query throttle shared DRF's `throttle_anon_<ident>`
    history with every metadata view, so the network's health polling
    (/info, /datasets) spent the same budget as g_variants queries."""

    class _Req:
        META = {'REMOTE_ADDR': '203.0.113.9'}

        class user:
            is_authenticated = False

    def test_query_history_is_not_the_anon_history(self):
        from rest_framework.throttling import AnonRateThrottle

        query_key = QueryRateThrottle().get_cache_key(self._Req(), None)
        anon_key = AnonRateThrottle().get_cache_key(self._Req(), None)
        self.assertIsNotNone(query_key)
        self.assertNotEqual(query_key, anon_key)

    def test_spending_the_anon_budget_leaves_the_query_budget_whole(self):
        from django.core.cache import cache
        from rest_framework.throttling import AnonRateThrottle

        cache.clear()
        req = self._Req()
        anon = AnonRateThrottle()
        for _ in range(anon.num_requests + 5):
            anon.allow_request(req, None)
        self.assertFalse(AnonRateThrottle().allow_request(req, None))
        self.assertTrue(QueryRateThrottle().allow_request(req, None))


if __name__ == '__main__':
    unittest.main()
