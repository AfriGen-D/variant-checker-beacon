"""Every error body is a Beacon v2 error envelope (review 2026-10-22, G3).

Before: build_error_envelope() produced `meta` without `receivedRequestSummary`
(a required field of the Beacon response meta), a DRF 429 was
{"detail": "Request was throttled..."} and the rate-limit middleware's 429 was
{"error": ..., "message": ...}. A client parsing Beacon errors got three shapes.

Needs Django + DRF:

    python3 -m unittest beacon_api.test_error_envelopes -v
"""
import json
import unittest

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        SECRET_KEY='test-only',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        BEACON_RATE_LIMITS={'query': '1/hour'},
        BEACON_API_ID='org.test.beacon',
        ALLOWED_HOSTS=['*'],
    )
    import django

    django.setup()

from django.core.cache import cache  # noqa: E402
from django.test import RequestFactory, SimpleTestCase, override_settings  # noqa: E402
from rest_framework import exceptions  # noqa: E402

from beacon_api.middleware import RateLimitMiddleware  # noqa: E402
from beacon_api.utils import build_error_envelope, custom_exception_handler  # noqa: E402

BEACON = override_settings(DEBUG=False, BEACON_API_ID='org.test.beacon', BEACON_RATE_LIMITS={})

SUMMARY_KEYS = {'apiVersion', 'requestedGranularity', 'requestedSchemas', 'pagination'}


def assert_error_envelope(test, body, code):
    test.assertEqual(set(body), {'meta', 'error'}, body)
    test.assertEqual(body['error']['errorCode'], code)
    test.assertIsInstance(body['error']['errorMessage'], str)
    test.assertTrue(body['error']['errorMessage'])
    test.assertEqual(body['meta']['beaconId'], 'org.test.beacon')
    test.assertTrue(SUMMARY_KEYS <= set(body['meta']['receivedRequestSummary']), body['meta'])


@BEACON
class BuildErrorEnvelopeTests(SimpleTestCase):
    def test_meta_carries_a_received_request_summary(self):
        assert_error_envelope(self, build_error_envelope(400, 'bad'), 400)

    def test_the_summary_echoes_a_valid_requested_granularity(self):
        body = build_error_envelope(400, 'bad', {'requestedGranularity': 'count'})
        self.assertEqual(body['meta']['receivedRequestSummary']['requestedGranularity'], 'count')

    def test_an_invalid_granularity_is_not_reflected(self):
        body = build_error_envelope(400, 'bad', {'requestedGranularity': '<script>'})
        self.assertEqual(body['meta']['receivedRequestSummary']['requestedGranularity'], 'boolean')

    def test_code_and_message_are_preserved(self):
        body = build_error_envelope('501', 'I cannot answer')
        self.assertEqual(body['error'], {'errorCode': 501, 'errorMessage': 'I cannot answer'})


@BEACON
class DrfErrorHandlerTests(SimpleTestCase):
    def handle(self, exc):
        return custom_exception_handler(exc, {})

    def test_a_throttled_request_is_a_beacon_envelope_and_keeps_retry_after(self):
        response = self.handle(exceptions.Throttled(wait=3480))
        self.assertEqual(response.status_code, 429)
        assert_error_envelope(self, response.data, 429)
        self.assertIn('3480', response.data['error']['errorMessage'])
        self.assertEqual(response['Retry-After'], '3480')

    def test_a_not_found_is_a_beacon_envelope(self):
        response = self.handle(exceptions.NotFound())
        self.assertEqual(response.status_code, 404)
        assert_error_envelope(self, response.data, 404)

    def test_a_server_error_does_not_leak_its_message(self):
        response = self.handle(exceptions.APIException('db password is hunter2'))
        self.assertEqual(response.status_code, 500)
        assert_error_envelope(self, response.data, 500)
        self.assertNotIn('hunter2', json.dumps(response.data))

    def test_an_unhandled_exception_stays_unhandled(self):
        self.assertIsNone(self.handle(ValueError('boom')))


@BEACON
class MiddlewareThrottleTests(SimpleTestCase):
    def test_the_middleware_429_is_a_beacon_envelope(self):
        cache.clear()
        mw = RateLimitMiddleware(lambda request: None)
        request = RequestFactory().get('/api/g_variants', REMOTE_ADDR='203.0.113.7')
        mw.rate_limits = {mw.get_endpoint_key(request.path): '1/hour'}
        self.assertIsNone(mw(request))
        response = mw(request)
        self.assertEqual(response.status_code, 429)
        assert_error_envelope(self, json.loads(response.content), 429)
        self.assertEqual(response['Content-Type'], 'application/json')


if __name__ == '__main__':
    unittest.main()
