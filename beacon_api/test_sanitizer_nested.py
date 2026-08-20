"""Regression tests for QueryParameterSanitizer against nested POST bodies.

The bug under test
------------------
``QueryParameterSanitizer.sanitize`` stringified every value before matching
INJECTION_PATTERNS. ``str()`` on a dict renders Python's repr::

    str({'referenceName': '22'}) == "{'referenceName': '22'}"

whose single quotes match ``[;\\'"\\\\]``, so a spec-shaped Beacon v2 POST body
was rejected with "Invalid characters detected in query" -- an injection
verdict on punctuation the sanitizer itself introduced. GET was unaffected
because ``request.GET.dict()`` produces flat strings, so in production
``GET /api/g_variants?...`` answered correctly while the equivalent POST 400'd.

These tests pin both halves: nested bodies survive, and operator injection is
still refused.
"""
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth'],
        DATABASES={},
        USE_TZ=True,
    )
    django.setup()

import unittest  # noqa: E402

from rest_framework.exceptions import ValidationError  # noqa: E402

from beacon_api.validators import QueryParameterSanitizer  # noqa: E402


class NestedBodySurvivesSanitization(unittest.TestCase):
    def test_spec_shaped_post_body_is_accepted(self):
        body = {
            'query': {
                'requestParameters': {
                    'referenceName': '22',
                    'start': [16050074],
                    'referenceBases': 'A',
                    'alternateBases': 'G',
                },
                'requestedGranularity': 'boolean',
            }
        }

        sanitized = QueryParameterSanitizer.sanitize_query_params(body)

        params = sanitized['query']['requestParameters']
        self.assertEqual(params['referenceName'], '22')
        self.assertEqual(params['referenceBases'], 'A')
        self.assertEqual(params['start'], ['16050074'])

    def test_nested_structure_is_preserved_not_flattened(self):
        sanitized = QueryParameterSanitizer.sanitize_query_params(
            {'query': {'requestParameters': {'referenceName': '1'}}}
        )

        self.assertIsInstance(sanitized['query'], dict)
        self.assertIsInstance(sanitized['query']['requestParameters'], dict)

    def test_flat_get_style_params_still_work(self):
        sanitized = QueryParameterSanitizer.sanitize_query_params(
            {'referenceName': '22', 'start': '16050074'}
        )

        self.assertEqual(sanitized, {'referenceName': '22', 'start': '16050074'})


class InjectionIsStillRejected(unittest.TestCase):
    def test_operator_key_nested_in_body_is_rejected(self):
        # The whole point of recursing: a Mongo operator buried in a nested
        # object must still be caught, not smuggled past on a container type.
        with self.assertRaises(ValidationError):
            QueryParameterSanitizer.sanitize_query_params(
                {'query': {'requestParameters': {'$where': 'sleep(1000)'}}}
            )

    def test_operator_value_nested_in_body_is_rejected(self):
        with self.assertRaises(ValidationError):
            QueryParameterSanitizer.sanitize_query_params(
                {'query': {'diseaseCode': {'$regex': '^A'}}}
            )

    def test_operator_inside_a_list_is_rejected(self):
        with self.assertRaises(ValidationError):
            QueryParameterSanitizer.sanitize_query_params(
                {'filters': [{'id': '$ne'}]}
            )

    def test_quote_injection_in_a_leaf_is_rejected(self):
        with self.assertRaises(ValidationError):
            QueryParameterSanitizer.sanitize_query_params(
                {'referenceName': "22'; drop"}
            )

    def test_script_tag_in_a_leaf_is_rejected(self):
        with self.assertRaises(ValidationError):
            QueryParameterSanitizer.sanitize_query_params(
                {'referenceName': '<script>alert(1)</script>'}
            )
