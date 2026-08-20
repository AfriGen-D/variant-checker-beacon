"""A spec-shaped POST body must produce the SAME query as the equivalent GET.

The defect this pins
--------------------
Beacon v2 sends query parameters nested::

    {"query": {"requestParameters": {"referenceName": "1", "start": 12345},
               "requestedGranularity": "boolean"}}

Nothing in the app ever read ``requestParameters`` — grep it across beacon_api
and the only hits are a docstring and a comment. The view built its Mongo query
from TOP-LEVEL keys, found none, and queried the whole collection.

Measured on a real stack before this fix (100 variants loaded):

    POST {"query":{"requestParameters":{"referenceName":"7","start":999999999}}}
      -> exists: true, numTotalResults: 100     # an impossible locus
    POST {}
      -> exists: true, numTotalResults: 100     # identical

So a spec-conformant client got a confident YES for a locus that cannot exist.
Fixing the sanitizer alone (which previously 400'd these bodies) would have
turned an honest refusal into that wrong answer — strictly worse. The two
belong in one change.

Django-free: pure dict manipulation, no DRF import, so it runs in the fast gate.

    python3 -m unittest beacon_api.test_request_body -v
"""
import unittest

from beacon_api.request_body import flatten_beacon_request


class SpecShapedBody(unittest.TestCase):
    def test_request_parameters_are_lifted_to_the_top(self):
        out = flatten_beacon_request({
            'query': {
                'requestParameters': {'referenceName': '1', 'start': 12345},
                'requestedGranularity': 'boolean',
            }
        })
        self.assertEqual(out['referenceName'], '1')
        self.assertEqual(out['start'], 12345)

    def test_sibling_query_keys_survive(self):
        out = flatten_beacon_request({
            'query': {'requestParameters': {'referenceName': '1'},
                      'requestedGranularity': 'count'}
        })
        self.assertEqual(out['requestedGranularity'], 'count')

    def test_filters_are_preserved_wherever_they_sit(self):
        nested = flatten_beacon_request({'query': {'filters': [{'id': 'NCIT:C16576'}]}})
        top = flatten_beacon_request({'filters': [{'id': 'NCIT:C16576'}]})
        self.assertEqual(nested['filters'], [{'id': 'NCIT:C16576'}])
        self.assertEqual(top['filters'], [{'id': 'NCIT:C16576'}])

    def test_pagination_is_preserved_wherever_it_sits(self):
        nested = flatten_beacon_request({'query': {'pagination': {'skip': 2, 'limit': 5}}})
        self.assertEqual(nested['pagination'], {'skip': 2, 'limit': 5})


class FlatBodyIsUnchanged(unittest.TestCase):
    """GET-style and already-flat POST bodies must pass through untouched."""

    def test_flat_body_passes_through(self):
        body = {'referenceName': '1', 'start': 12345, 'assemblyId': 'GRCh38'}
        self.assertEqual(flatten_beacon_request(body), body)

    def test_empty_body_stays_empty(self):
        self.assertEqual(flatten_beacon_request({}), {})

    def test_non_dict_is_returned_unchanged(self):
        self.assertEqual(flatten_beacon_request(None), None)
        self.assertEqual(flatten_beacon_request([1, 2]), [1, 2])


class TopLevelWins(unittest.TestCase):
    """An explicit top-level key is the caller being unambiguous — respect it."""

    def test_top_level_beats_nested(self):
        out = flatten_beacon_request({
            'referenceName': 'X',
            'query': {'requestParameters': {'referenceName': '1'}},
        })
        self.assertEqual(out['referenceName'], 'X')


class TheImpossibleLocusRegression(unittest.TestCase):
    """The exact body measured returning 100/100 on a real stack."""

    def test_impossible_locus_reaches_the_query(self):
        out = flatten_beacon_request({
            'query': {'requestParameters': {'assemblyId': 'GRCh38',
                                            'referenceName': '7',
                                            'start': 999999999}}
        })
        self.assertEqual(out['referenceName'], '7')
        self.assertEqual(out['start'], 999999999)
        self.assertNotIn('query', out)


if __name__ == '__main__':
    unittest.main()
