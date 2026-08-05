"""
Unit tests for RateLimitMiddleware.

Deliberately standalone: these exercise pure request-budget logic and must not
require MongoDB, so the module configures a minimal settings object when run
outside the full Django test setup.

    python -m beacon_api.test_middleware
"""
import unittest
from unittest import mock

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-only',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        BEACON_RATE_LIMITS={},
    )
    import django

    django.setup()

from django.core.cache import cache  # noqa: E402

from beacon_api import middleware  # noqa: E402
from beacon_api.middleware import RateLimitMiddleware  # noqa: E402


class FakeClock:
    """
    Stands in for the `time` module inside the middleware's namespace only.

    Patching the real time.time() would also move LocMemCache's expiry clock,
    which would expire the counter for us and let a broken implementation pass.
    """

    def __init__(self, now):
        self.now = now

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RateLimitWindowTests(unittest.TestCase):
    """The window must roll over on schedule, whatever the cache does."""

    def setUp(self):
        cache.clear()
        self.mw = RateLimitMiddleware(lambda request: None)

    def _spend(self, n, limit='5/hour', ip='1.2.3.4', endpoint='discovery'):
        return [self.mw.check_rate_limit(ip, endpoint, limit) for _ in range(n)]

    def test_allows_up_to_the_limit_then_blocks(self):
        self.assertTrue(all(self._spend(5)))
        self.assertFalse(self.mw.check_rate_limit('1.2.3.4', 'discovery', '5/hour'))

    def test_window_rolls_over_even_when_the_cache_key_never_expires(self):
        """
        Regression test for the federation outage: a client polling more often
        than once per period had its key's TTL pushed forward by every accepted
        request, so the window never ended and the client stayed blocked.

        Only the middleware's clock is advanced — the cache keeps running on
        real time, so nothing here ever actually expires, which is precisely the
        condition that used to latch. Rolling over must therefore come from the
        key, not from the TTL.
        """
        clock = FakeClock(1_000_000.0)
        with mock.patch.object(middleware, 'time', clock):
            self.assertTrue(all(self._spend(5)))
            self.assertFalse(self.mw.check_rate_limit('1.2.3.4', 'discovery', '5/hour'))

            clock.advance(3600)  # next hour

            self.assertTrue(
                self.mw.check_rate_limit('1.2.3.4', 'discovery', '5/hour'),
                'client is still locked out after the window elapsed',
            )

    def test_budgets_are_isolated_per_ip_and_per_endpoint(self):
        self.assertTrue(all(self._spend(5, endpoint='variants')))
        self.assertFalse(self.mw.check_rate_limit('1.2.3.4', 'variants', '5/hour'))

        # A different endpoint, and a different client, are unaffected.
        self.assertTrue(self.mw.check_rate_limit('1.2.3.4', 'discovery', '5/hour'))
        self.assertTrue(self.mw.check_rate_limit('9.9.9.9', 'variants', '5/hour'))

    def test_unparseable_limit_fails_open(self):
        self.assertTrue(self.mw.check_rate_limit('1.2.3.4', 'discovery', 'nonsense'))


class EndpointKeyTests(unittest.TestCase):
    def setUp(self):
        self.mw = RateLimitMiddleware(lambda request: None)

    def test_discovery_endpoints(self):
        for path in (
            '/api/info',
            '/api/service-info',
            '/api/configuration',
            '/api/entry_types',
            '/api/map',
            '/api/datasets',
            '/api/datasets/H3A_V6_AFR',
            '/api/filtering_terms',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.mw.get_endpoint_key(path), 'discovery')

    def test_data_endpoints_keep_their_own_budgets(self):
        self.assertEqual(self.mw.get_endpoint_key('/api/g_variants'), 'variants')
        self.assertEqual(self.mw.get_endpoint_key('/api/query/individuals'), 'query')
        self.assertEqual(self.mw.get_endpoint_key('/api/individuals'), 'individuals')

    def test_unknown_path_falls_back_to_default(self):
        self.assertEqual(self.mw.get_endpoint_key('/api/something_else'), 'default')


if __name__ == '__main__':
    unittest.main()
