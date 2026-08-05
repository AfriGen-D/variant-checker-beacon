"""
Regression tests for pagination, filters handling, and query-cost bounds.

Standalone and MongoDB-free, following the pattern in
``beacon_api/test_query_semantics.py`` and ``beacon_api/test_query_injection.py``:
these exercise ``beacon_api.pagination``, ``beacon_api.filters`` and
``beacon_api.query_cost``, none of which imports Django, DRF or MongoEngine, so
they run with plain unittest and need no settings module, no database and no
network.

    python3 -m unittest beacon_api.test_pagination_filters -v

The bugs under test
-------------------
1. **Pagination was echoed but never applied.** ``BeaconQuerySerializer`` had no
   ``skip``/``limit`` fields, so both were dropped — while
   ``build_received_request_summary`` unconditionally returned
   ``{'skip': 0, 'limit': 10}``. Every response therefore claimed a page had
   been applied that never was, and a client paging with ``skip`` silently
   received page 1 forever.

2. **``filters`` was accepted-looking and ignored.** The serializer had no
   ``filters`` field either, so an ontology-term filter was dropped without
   error and the beacon answered the *unfiltered* question with a 200. On a
   discovery service that is a correctness failure: "YES" for the whole panel
   is indistinguishable from "YES" for the cohort the client asked about.

3. **An unparameterized ``/g_variants`` scanned the whole collection.**
   Production returned HTTP 504 after 30.7s, and it was the one failing GA4GH
   ``beacon-verifier`` check ("Genomic Variants all entries": operation timed
   out). The existing guard only fired when a *position* key was present, so a
   request with no parameters skipped it entirely. Unauthenticated and
   trivially repeatable — four concurrent requests saturate a 4-worker API.
"""
import unittest

from beacon_api.filters import (
    MAX_ECHOED_FILTERS,
    UnsupportedFilters,
    has_filters,
    normalize_filters,
    reject_filters,
)
from beacon_api.pagination import (
    DEFAULT_LIMIT,
    DEFAULT_SKIP,
    InvalidPagination,
    MAX_LIMIT,
    MAX_SKIP,
    clamp_limit,
    paginate,
    parse_pagination,
)
from beacon_api.query_cost import (
    QUERY_LOCUS,
    QUERY_PARTIAL,
    QUERY_UNBOUNDED,
    allows_per_dataset_attribution,
    classify_variant_query,
)
from beacon_api.query_semantics import POSITION_FILTER_KEYS, build_position_filter


# ---------------------------------------------------------------------------
# Gap 1 — pagination is real
# ---------------------------------------------------------------------------

class PaginationParsingTests(unittest.TestCase):

    def test_absent_parameters_yield_defaults(self):
        self.assertEqual(parse_pagination({}), (DEFAULT_SKIP, DEFAULT_LIMIT))

    def test_query_string_values_are_parsed(self):
        # GET params arrive as text, never as ints.
        self.assertEqual(parse_pagination({'skip': '20', 'limit': '5'}), (20, 5))

    def test_json_body_integers_are_parsed(self):
        self.assertEqual(parse_pagination({'skip': 20, 'limit': 5}), (20, 5))

    def test_skip_zero_is_honoured_not_treated_as_absent(self):
        # A falsy-check bug here would be invisible, since 0 is also the
        # default — pin it down explicitly.
        self.assertEqual(parse_pagination({'skip': 0, 'limit': 7}), (0, 7))

    def test_float_with_integral_value_is_accepted(self):
        self.assertEqual(parse_pagination({'limit': 5.0}), (0, 5))

    def test_fractional_limit_is_rejected_not_truncated(self):
        # Truncating 5.9 to 5 would serve a different page than was requested
        # while the echo claimed otherwise.
        with self.assertRaises(InvalidPagination):
            parse_pagination({'limit': 5.9})

    def test_non_numeric_string_is_rejected(self):
        with self.assertRaises(InvalidPagination):
            parse_pagination({'skip': 'abc'})

    def test_negative_value_is_rejected(self):
        with self.assertRaises(InvalidPagination):
            parse_pagination({'skip': '-1'})
        with self.assertRaises(InvalidPagination):
            parse_pagination({'limit': -5})

    def test_booleans_are_rejected_rather_than_read_as_ints(self):
        # bool is an int subclass; True must not silently become limit=1.
        with self.assertRaises(InvalidPagination):
            parse_pagination({'limit': True})

    def test_structured_values_are_rejected(self):
        # A POST body is arbitrary JSON, so these are reachable shapes and
        # must not reach int() (500) or a Mongo query (operator injection).
        for bad in ({'$gt': 0}, [1], (1,), {'a': 1}):
            with self.assertRaises(InvalidPagination):
                parse_pagination({'skip': bad})

    def test_non_dict_params_yield_defaults(self):
        self.assertEqual(parse_pagination(None), (DEFAULT_SKIP, DEFAULT_LIMIT))
        self.assertEqual(parse_pagination([1, 2]), (DEFAULT_SKIP, DEFAULT_LIMIT))


class PaginationBoundsTests(unittest.TestCase):
    """Every parameter here is attacker-controlled on a public endpoint."""

    def test_limit_above_the_cap_is_clamped(self):
        # An over-large limit means "give me everything"; clamping it and
        # reporting the applied value is an honest answer.
        _, limit = parse_pagination({'limit': MAX_LIMIT + 5000})
        self.assertEqual(limit, MAX_LIMIT)

    def test_skip_above_the_cap_is_refused_not_clamped(self):
        # Silently reducing an offset would serve a DIFFERENT page than the one
        # requested while the response claimed otherwise — the exact class of
        # lie this work removes. It must be an error.
        with self.assertRaises(InvalidPagination):
            parse_pagination({'skip': MAX_SKIP + 1})

    def test_skip_exactly_at_the_cap_is_allowed(self):
        skip, _ = parse_pagination({'skip': MAX_SKIP})
        self.assertEqual(skip, MAX_SKIP)

    def test_limit_zero_does_not_mean_unlimited(self):
        # Beacon v2 reads limit=0 as "no limit". On a public beacon in front of
        # ~42M documents that is a denial-of-service switch, so it maps to the
        # bounded default instead.
        self.assertEqual(clamp_limit(0), DEFAULT_LIMIT)
        self.assertLessEqual(clamp_limit(0), MAX_LIMIT)

    def test_default_limit_is_itself_bounded(self):
        # Guards against someone "restoring spec behaviour" by making the
        # default unbounded.
        self.assertLessEqual(DEFAULT_LIMIT, MAX_LIMIT)
        self.assertGreater(DEFAULT_LIMIT, 0)


class PaginationSlicingTests(unittest.TestCase):

    ITEMS = list(range(10))

    def test_first_page(self):
        self.assertEqual(paginate(self.ITEMS, 0, 3), [0, 1, 2])

    def test_second_page_is_actually_different(self):
        # The whole bug: skip used to have no effect, so page 2 == page 1.
        first = paginate(self.ITEMS, 0, 3)
        second = paginate(self.ITEMS, 3, 3)
        self.assertEqual(second, [3, 4, 5])
        self.assertNotEqual(first, second)

    def test_skip_past_the_end_is_empty_not_wrapped(self):
        self.assertEqual(paginate(self.ITEMS, 100, 3), [])

    def test_limit_larger_than_the_collection_returns_all(self):
        self.assertEqual(paginate(self.ITEMS, 0, 1000), self.ITEMS)

    def test_default_pagination_is_a_no_op_for_existing_callers(self):
        # Callers that omit skip/limit must see exactly what they saw before
        # pagination existed.
        skip, limit = parse_pagination({})
        self.assertEqual(paginate(self.ITEMS, skip, limit), self.ITEMS)


# ---------------------------------------------------------------------------
# Gap 2 — filters are refused, never silently dropped
# ---------------------------------------------------------------------------

class FilterNormalizationTests(unittest.TestCase):

    def test_single_term_string(self):
        self.assertEqual(normalize_filters('NCIT:C16576'), ['NCIT:C16576'])

    def test_comma_separated_get_form(self):
        self.assertEqual(
            normalize_filters('NCIT:C16576,HP:0001250'),
            ['NCIT:C16576', 'HP:0001250'],
        )

    def test_list_of_ids_post_form(self):
        self.assertEqual(normalize_filters(['HP:0001250']), ['HP:0001250'])

    def test_list_of_filter_objects_post_form(self):
        raw = [{'id': 'HP:0001250', 'operator': '=', 'value': 'x'}]
        self.assertEqual(normalize_filters(raw), ['HP:0001250'])

    def test_single_filter_object(self):
        self.assertEqual(normalize_filters({'id': 'HP:0001250'}), ['HP:0001250'])

    def test_absent_and_empty_values_are_no_filters(self):
        # A bare `?filters=` narrows nothing and must not trip the rejection.
        for raw in (None, '', '   ', [], ',,', [{}], [{'id': ''}]):
            self.assertEqual(normalize_filters(raw), [], repr(raw))


class FilterRejectionTests(unittest.TestCase):

    def test_request_without_filters_is_untouched(self):
        reject_filters({'referenceName': '1', 'start': 100})  # must not raise

    def test_empty_filters_value_is_not_a_filter(self):
        reject_filters({'filters': ''})  # must not raise

    def test_filters_are_rejected_rather_than_silently_dropped(self):
        # THE bug: this used to return 200 with an answer computed over the
        # whole unfiltered panel.
        with self.assertRaises(UnsupportedFilters):
            reject_filters({'filters': 'NCIT:C16576'})

    def test_spec_shaped_post_filters_are_rejected(self):
        with self.assertRaises(UnsupportedFilters):
            reject_filters({'filters': [{'id': 'HP:0001250'}]})

    def test_error_names_the_unresolvable_terms(self):
        # A client has to be able to tell WHICH term was refused.
        with self.assertRaises(UnsupportedFilters) as ctx:
            reject_filters({'filters': 'HP:0001250'})
        self.assertIn('HP:0001250', str(ctx.exception))

    def test_error_explains_why_rather_than_just_refusing(self):
        with self.assertRaises(UnsupportedFilters) as ctx:
            reject_filters({'filters': 'HP:0001250'})
        message = str(ctx.exception).lower()
        self.assertIn('filtering terms', message)
        self.assertIn('/filtering_terms', str(ctx.exception))

    def test_echoed_terms_are_bounded(self):
        # `filters` is attacker-controlled; the 400 must not reflect an
        # unbounded payload back.
        terms = [f'TERM:{i}' for i in range(200)]
        with self.assertRaises(UnsupportedFilters) as ctx:
            reject_filters({'filters': terms})
        message = str(ctx.exception)
        self.assertIn('...', message)
        self.assertNotIn('TERM:199', message)
        self.assertEqual(message.count('TERM:'), MAX_ECHOED_FILTERS)

    def test_long_term_is_truncated_in_the_message(self):
        with self.assertRaises(UnsupportedFilters) as ctx:
            reject_filters({'filters': 'A' * 5000})
        self.assertLess(len(str(ctx.exception)), 1000)

    def test_has_filters_matches_the_rejection(self):
        # These two must never disagree, or a request gets checked one way and
        # answered the other.
        for params in ({}, {'filters': ''}, {'filters': 'X:1'},
                       {'filters': [{'id': 'X:1'}]}, {'filters': []}):
            expected = has_filters(params)
            try:
                reject_filters(params)
                raised = False
            except UnsupportedFilters:
                raised = True
            self.assertEqual(expected, raised, repr(params))


# ---------------------------------------------------------------------------
# Unbounded-query DoS — an unparameterized /g_variants must stay bounded
# ---------------------------------------------------------------------------

def built_variant_query(reference_name=None, start=None, end=None,
                        reference_bases=None, alternate_bases=None,
                        assembly_id='GRCh38'):
    """The mongo_query that ``variant_query_boolean`` builds for a request.

    Mirrors beacon_api/views_boolean.py::variant_query_boolean so query
    *construction* can be asserted without Django, DRF or a live MongoDB.
    Note ``assembly_id`` defaults to GRCh38 exactly as the serializer does —
    that default is why a parameterless request produced a non-empty query and
    so looked "filtered" to the old guard.
    """
    query = {}
    if reference_name:
        bare = reference_name[3:] if reference_name.startswith('chr') else reference_name
        query['reference_name__in'] = [bare, f'chr{bare}']
    query.update(build_position_filter(start, end))
    if reference_bases:
        query['reference_bases'] = reference_bases
    if alternate_bases:
        query['alternate_bases'] = alternate_bases
    if assembly_id:
        query['assembly_id'] = assembly_id
    return query


class QueryClassificationTests(unittest.TestCase):

    def _classify(self, **kwargs):
        return classify_variant_query(
            built_variant_query(**kwargs), POSITION_FILTER_KEYS
        )

    def test_parameterless_request_is_classified_unbounded(self):
        # THE production bug: GET /api/g_variants with no parameters. It built
        # {'assembly_id': 'GRCh38'} — non-empty, so it looked like a real
        # filter — and ran the per-dataset attribution loop over 42M documents.
        self.assertEqual(self._classify(), QUERY_UNBOUNDED)

    def test_assembly_only_carries_no_selectivity(self):
        # assemblyId is applied to every single query, so it can never be the
        # thing that makes a query cheap. Treating it as a constraint is
        # exactly how the parameterless case escaped the old guard.
        self.assertEqual(self._classify(assembly_id='GRCh37'), QUERY_UNBOUNDED)

    def test_reference_name_only_is_not_locus_selective(self):
        # A full-chromosome scan: millions of candidate documents, so the
        # per-dataset probes are still unaffordable.
        self.assertEqual(self._classify(reference_name='1'), QUERY_PARTIAL)

    def test_alleles_without_a_position_are_not_locus_selective(self):
        self.assertEqual(
            self._classify(reference_bases='A', alternate_bases='T'),
            QUERY_PARTIAL,
        )

    def test_chromosome_plus_position_is_locus_selective(self):
        self.assertEqual(
            self._classify(reference_name='1', start=1000), QUERY_LOCUS
        )

    def test_chromosome_plus_range_is_locus_selective(self):
        self.assertEqual(
            self._classify(reference_name='1', start=1000, end=2000),
            QUERY_LOCUS,
        )

    def test_chr_prefixed_chromosome_is_locus_selective(self):
        self.assertEqual(
            self._classify(reference_name='chr7', start=500), QUERY_LOCUS
        )


class AttributionBoundTests(unittest.TestCase):
    """The per-dataset ``dataset_ids`` loop is what actually cost 30.7s."""

    def _allows(self, **kwargs):
        return allows_per_dataset_attribution(
            classify_variant_query(built_variant_query(**kwargs), POSITION_FILTER_KEYS)
        )

    def test_parameterless_request_does_not_run_the_attribution_loop(self):
        # `dataset_ids` is unset on many stored variants, so a probe that
        # matches nothing walks all ~42M documents before it can answer "no" —
        # once per dataset. This is the assertion that keeps the 504 fixed.
        self.assertFalse(self._allows())

    def test_reference_name_only_does_not_run_the_attribution_loop(self):
        self.assertFalse(self._allows(reference_name='1'))

    def test_locus_query_still_runs_the_attribution_loop(self):
        # The fix must not cost real queries their per-dataset breakdown: a
        # locus query narrows to a handful of documents first, so the probes
        # are cheap and the frontend keeps its dataset attribution.
        self.assertTrue(self._allows(reference_name='1', start=1000))

    def test_only_locus_queries_are_ever_allowed(self):
        for query_class in (QUERY_UNBOUNDED, QUERY_PARTIAL):
            self.assertFalse(allows_per_dataset_attribution(query_class))
        self.assertTrue(allows_per_dataset_attribution(QUERY_LOCUS))


class ParameterlessRequestIsAnsweredNotRefusedTests(unittest.TestCase):
    """Beacon v2 defines a parameterless /g_variants as the "all entries"
    request, and the GA4GH verifier issues exactly that. Answering 400 would
    trade a timeout for a conformance failure, so it must be *classified* and
    bounded, never rejected."""

    def test_unbounded_is_a_recognised_class_not_an_error(self):
        query = built_variant_query()
        self.assertEqual(
            classify_variant_query(query, POSITION_FILTER_KEYS), QUERY_UNBOUNDED
        )

    def test_the_old_position_guard_did_not_fire_on_it(self):
        # Reproduces why the bug survived: the guard keyed on a position key,
        # and a parameterless request builds none.
        query = built_variant_query()
        old_guard_fires = (
            any(k in query for k in POSITION_FILTER_KEYS)
            and 'reference_name__in' not in query
        )
        self.assertFalse(
            old_guard_fires,
            'the pre-fix guard is expected to miss the parameterless request',
        )

    def test_the_response_page_is_bounded_by_default(self):
        # Whatever the classification, the returned collection is capped.
        skip, limit = parse_pagination({})
        self.assertLessEqual(limit, MAX_LIMIT)
        self.assertEqual(skip, 0)


if __name__ == '__main__':
    unittest.main()
