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


if __name__ == '__main__':
    unittest.main()
