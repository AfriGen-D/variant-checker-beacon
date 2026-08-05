"""
Regression tests for genomic position query semantics.

Standalone and MongoDB-free: these exercise the query-*construction* logic in
``beacon_api.query_semantics`` (which imports no Django, DRF or MongoEngine),
so they run with plain unittest and need no settings module, no database and
no network.

    python3 -m unittest beacon_api.test_query_semantics -v

The bug under test
------------------
Variants are stored 0-based half-open (``start = POS-1``,
``end = POS-1+len(REF)``). The view previously built the position filter as::

    mongo_query['start__lte'] = position_end
    mongo_query['end__gte'] = position_start

which is closed-interval overlap. Against half-open storage that makes a
variant occupying ``[P-1, P)`` match a query for position ``P`` — the beacon
answering YES for the base immediately after the real variant. Every test
below that asserts a non-match at an adjacent base fails against that old
filter and passes against the half-open one.
"""
import unittest

from beacon_api.query_semantics import (
    POSITION_FILTER_KEYS,
    build_position_filter,
)


def stored_variant(pos, ref='A'):
    """A variant as the VCF transform stores it, from a 1-based VCF POS.

    Mirrors afrigend-beacon2-tools/vcf_transform/vcf_to_beacon.py:196-197.
    """
    return {'start': pos - 1, 'end': pos - 1 + len(ref)}


def matches(variant, query_filter):
    """Evaluate a MongoEngine-style filter dict against one variant doc.

    Supports only the operators build_position_filter emits; an unexpected
    operator raises rather than silently passing, so a change in emitted
    operators cannot quietly weaken these tests.
    """
    for key, value in query_filter.items():
        field, _, op = key.partition('__')
        actual = variant[field]
        if op == 'lt':
            ok = actual < value
        elif op == 'gt':
            ok = actual > value
        elif op == 'lte':
            ok = actual <= value
        elif op == 'gte':
            ok = actual >= value
        elif op == '':
            ok = actual == value
        else:
            raise AssertionError(f'unsupported operator in filter key {key!r}')
        if not ok:
            return False
    return True


def legacy_position_filter(start, end=None):
    """The pre-fix (buggy) closed-interval filter, kept for contrast.

    Used by test_legacy_filter_had_the_off_by_one so the regression these
    tests guard is asserted explicitly rather than only implied.
    """
    position_end = end if end is not None else start
    return {'start__lte': position_end, 'end__gte': start}


class PointQueryTests(unittest.TestCase):
    """A point query asks about the single base [start, start+1)."""

    # Beacon 0-based coordinate of the base under test; the variant that
    # genuinely sits there comes from 1-based VCF POS 1001.
    QUERY_START = 1000

    def test_matches_variant_at_exactly_that_position(self):
        f = build_position_filter(self.QUERY_START)
        self.assertTrue(matches(stored_variant(1001), f))

    def test_does_not_match_variant_one_base_earlier(self):
        # VCF POS 1000 -> stored [999, 1000). Its end == our query start, and
        # under half-open semantics a shared boundary is NOT an overlap.
        # This is the exact case the old lte/gte filter got wrong.
        f = build_position_filter(self.QUERY_START)
        self.assertFalse(matches(stored_variant(1000), f))

    def test_does_not_match_variant_one_base_later(self):
        # VCF POS 1002 -> stored [1001, 1002), starts after our single base.
        f = build_position_filter(self.QUERY_START)
        self.assertFalse(matches(stored_variant(1002), f))

    def test_is_not_the_degenerate_empty_interval(self):
        # [start, start) would match nothing at all. Guards against a naive
        # strict-inequality swap that forgets the +1.
        f = build_position_filter(self.QUERY_START)
        self.assertEqual(f['start__lt'], self.QUERY_START + 1)
        self.assertEqual(f['end__gt'], self.QUERY_START)

    def test_matches_multi_base_deletion_spanning_the_position(self):
        # VCF POS 998 with REF 'ACGT' -> stored [997, 1001), which covers 1000.
        f = build_position_filter(self.QUERY_START)
        self.assertTrue(matches(stored_variant(998, ref='ACGT'), f))

    def test_does_not_match_deletion_ending_exactly_at_the_position(self):
        # VCF POS 997 with REF 'ACGT' -> stored [996, 1000). end == 1000 is
        # exclusive, so base 1000 is outside it.
        f = build_position_filter(self.QUERY_START)
        self.assertFalse(matches(stored_variant(997, ref='ACGT'), f))


class RangeQueryTests(unittest.TestCase):
    """A range query asks about [start, end), with end exclusive."""

    START = 2000
    END = 2010

    def _f(self):
        return build_position_filter(self.START, self.END)

    def test_includes_variant_at_the_start_boundary(self):
        # Stored [2000, 2001) — the first base of the range.
        self.assertTrue(matches({'start': 2000, 'end': 2001}, self._f()))

    def test_includes_variant_at_the_last_base_inside_the_range(self):
        # Stored [2009, 2010) — the last base before the exclusive end.
        self.assertTrue(matches({'start': 2009, 'end': 2010}, self._f()))

    def test_excludes_variant_starting_at_the_exclusive_end(self):
        # Stored [2010, 2011) — end is exclusive, so this is outside.
        self.assertFalse(matches({'start': 2010, 'end': 2011}, self._f()))

    def test_excludes_variant_ending_exactly_at_the_start(self):
        # Stored [1999, 2000) — abuts the range but shares only a boundary.
        self.assertFalse(matches({'start': 1999, 'end': 2000}, self._f()))

    def test_includes_variant_spanning_the_whole_range(self):
        self.assertTrue(matches({'start': 1990, 'end': 2020}, self._f()))

    def test_excludes_variant_entirely_before_the_range(self):
        self.assertFalse(matches({'start': 1000, 'end': 1001}, self._f()))

    def test_excludes_variant_entirely_after_the_range(self):
        self.assertFalse(matches({'start': 3000, 'end': 3001}, self._f()))


class FilterShapeTests(unittest.TestCase):

    def test_no_position_yields_no_filter(self):
        # A query without a position must not constrain start/end at all.
        self.assertEqual(build_position_filter(None), {})
        self.assertEqual(build_position_filter(None, 500), {})

    def test_emitted_keys_match_the_exported_constant(self):
        # views_boolean uses POSITION_FILTER_KEYS to decide whether a query is
        # positional (and therefore requires referenceName). If the emitted
        # keys and the constant drift apart, that guard silently stops firing.
        f = build_position_filter(100)
        self.assertEqual(set(f), set(POSITION_FILTER_KEYS))

    def test_end_equal_to_start_is_treated_as_a_point_query(self):
        # The serializer permits start == end; taken literally that is an
        # empty interval matching nothing. It must behave like a point query.
        f = build_position_filter(1000, 1000)
        self.assertEqual(f, build_position_filter(1000))
        self.assertTrue(matches(stored_variant(1001), f))

    def test_end_below_start_is_treated_as_a_point_query(self):
        f = build_position_filter(1000, 400)
        self.assertEqual(f, build_position_filter(1000))

    def test_zero_start_is_honoured_not_treated_as_absent(self):
        # start=0 is a legitimate 0-based coordinate and must not be
        # swallowed by a falsy check.
        f = build_position_filter(0)
        self.assertEqual(f, {'start__lt': 1, 'end__gt': 0})


class LegacyContrastTests(unittest.TestCase):
    """Pin down what the old filter did, so the fix cannot be undone quietly."""

    def test_legacy_filter_had_the_off_by_one(self):
        legacy = legacy_position_filter(1000)
        fixed = build_position_filter(1000)
        one_base_earlier = stored_variant(1000)  # stored [999, 1000)

        self.assertTrue(
            matches(one_base_earlier, legacy),
            'legacy closed-interval filter should exhibit the false positive',
        )
        self.assertFalse(
            matches(one_base_earlier, fixed),
            'fixed half-open filter must not match the preceding base',
        )

    def test_both_filters_agree_on_the_true_positive(self):
        # The fix must not lose real matches — only the spurious ones.
        at_position = stored_variant(1001)
        self.assertTrue(matches(at_position, legacy_position_filter(1000)))
        self.assertTrue(matches(at_position, build_position_filter(1000)))


if __name__ == '__main__':
    unittest.main()
