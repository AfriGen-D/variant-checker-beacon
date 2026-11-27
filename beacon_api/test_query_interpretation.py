"""G7(a): a point query with no alternate allele must say what was answered.

`referenceName` + `start` with no `alternateBases` is not a query type the
Beacon v2 spec defines. The beacon answers "is any variant at this position?";
the response states that in the spec's free-form top-level `info` block.

Needs Django + DRF:

    python3 -m unittest beacon_api.test_query_interpretation -v
"""
import unittest

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        SECRET_KEY='test-only',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        BEACON_API_ID='org.test.beacon',
        ALLOWED_HOSTS=['*'],
    )
    import django

    django.setup()

from beacon_api.query_semantics import describe_interpretation  # noqa: E402
from beacon_api.utils import build_query_envelope  # noqa: E402

POINT = {'referenceName': '11', 'start': 5227001}


class DescribeInterpretationTests(unittest.TestCase):
    def test_a_point_query_with_no_alleles_is_described_as_an_extension(self):
        info = describe_interpretation(POINT)['queryInterpretation']
        self.assertEqual(info['answered'], 'anyVariantAtPosition')
        self.assertFalse(info['definedByBeaconSpec'])
        self.assertIn('alternateBases', info['description'])

    def test_position_zero_is_a_position(self):
        self.assertIsNotNone(describe_interpretation({'referenceName': '1', 'start': 0}))

    def test_the_legacy_position_parameter_counts(self):
        self.assertIsNotNone(describe_interpretation({'referenceName': '1', 'position': 7}))

    def test_reference_bases_alone_do_not_make_it_a_defined_query(self):
        self.assertIsNotNone(describe_interpretation({**POINT, 'referenceBases': 'T'}))

    def test_an_allele_query_carries_no_note(self):
        self.assertIsNone(describe_interpretation({**POINT, 'alternateBases': 'A'}))

    def test_a_range_query_carries_no_note(self):
        self.assertIsNone(describe_interpretation({**POINT, 'end': 5227100}))

    def test_a_query_with_no_position_carries_no_note(self):
        self.assertIsNone(describe_interpretation({}))
        self.assertIsNone(describe_interpretation({'referenceName': '11'}))


class EnvelopeInfoTests(unittest.TestCase):
    def test_info_sits_at_the_top_level_of_the_envelope(self):
        body = build_query_envelope(exists=True, info=describe_interpretation(POINT))
        self.assertIn('queryInterpretation', body['info'])

    def test_no_info_key_when_there_is_nothing_to_say(self):
        self.assertNotIn('info', build_query_envelope(exists=True, info=None))


if __name__ == '__main__':
    unittest.main()
