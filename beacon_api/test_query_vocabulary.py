"""Regression tests for the silent-widening defect class.

The shape under test
--------------------
A parameter is declared, validated, and then never applied to the query. The
beacon answers a BROADER question than the one it was asked, returns HTTP 200,
and says nothing about having done so.

``beacon_api/filters.py`` already documents why that is a correctness failure
rather than a missing feature: a YES meaning "yes, somewhere in the whole panel"
is indistinguishable from "yes, in the cohort you asked about". It refuses the
``filters`` parameter for exactly this reason. These tests extend the same
judgement to the parameters that were left on the wrong side of that line.

Django-free by design, like test_query_semantics and test_assembly.

    python3 -m unittest beacon_api.test_query_vocabulary -v
"""
import unittest

from beacon_api.query_vocabulary import (
    UnknownSex,
    UnknownVariantType,
    canonical_sex,
    canonical_variant_type,
    variant_type_filter,
)


class CanonicalVariantType(unittest.TestCase):
    """The allow-list accepted SNP; the ingest transform writes SNV.

    So the correct term, the stored value, and the value the project's own
    testing guide advertises were all REJECTED with a 400, while DEL was
    accepted and then silently discarded.
    """

    def test_snv_the_stored_value_is_accepted(self):
        self.assertEqual(canonical_variant_type('SNV'), 'SNV')

    def test_snp_is_accepted_as_an_alias_for_snv(self):
        self.assertEqual(canonical_variant_type('SNP'), 'SNV')

    def test_matching_is_case_insensitive(self):
        self.assertEqual(canonical_variant_type('snv'), 'SNV')
        self.assertEqual(canonical_variant_type('del'), 'DEL')

    def test_structural_types_survive(self):
        for t in ('DEL', 'INS', 'DUP', 'INV', 'CNV'):
            self.assertEqual(canonical_variant_type(t), t)

    def test_an_unrecognised_type_is_refused(self):
        with self.assertRaises(UnknownVariantType):
            canonical_variant_type('NONSENSE')

    def test_blank_is_refused_rather_than_treated_as_no_filter(self):
        for value in ('', '   '):
            with self.assertRaises(UnknownVariantType):
                canonical_variant_type(value)


class VariantTypeFilter(unittest.TestCase):
    """The filter must be emitted, and must match every stored spelling.

    Which spelling is stored depends on who wrote the document: the ingest
    transform writes SNV (vcf_to_beacon.py:436) while the bundled test fixture
    writes SNP (load_boolean_test_data.py:52). Filtering on one canonical value
    would return a false negative against data written under the other — the
    exact defect this module exists to remove, reintroduced from the other
    side. So match with __in, as assembly and reference_name already do.
    """

    def test_filter_uses_the_in_operator_not_equality(self):
        self.assertEqual(list(variant_type_filter('SNV')), ['variant_type__in'])

    def test_equality_key_is_never_emitted(self):
        self.assertNotIn('variant_type', variant_type_filter('SNV'))

    def test_an_snv_query_also_matches_snp_stored_data(self):
        self.assertIn('SNP', variant_type_filter('SNV')['variant_type__in'])

    def test_an_snp_query_also_matches_snv_stored_data(self):
        self.assertIn('SNV', variant_type_filter('SNP')['variant_type__in'])

    def test_a_type_with_one_spelling_still_emits_a_list(self):
        self.assertEqual(variant_type_filter('DEL'), {'variant_type__in': ['DEL']})

    def test_filter_is_never_empty_for_a_supplied_value(self):
        self.assertNotEqual(variant_type_filter('DEL'), {})


class CanonicalSex(unittest.TestCase):
    """An unrecognised sex was dropped, so /query/individuals silently became
    'do you have anyone at all'."""

    def test_known_values_pass_through(self):
        for s in ('MALE', 'FEMALE', 'OTHER', 'UNKNOWN'):
            self.assertEqual(canonical_sex(s), s)

    def test_matching_is_case_insensitive(self):
        self.assertEqual(canonical_sex('male'), 'MALE')
        self.assertEqual(canonical_sex('Female'), 'FEMALE')

    def test_an_unrecognised_sex_is_refused_not_dropped(self):
        with self.assertRaises(UnknownSex):
            canonical_sex('yes')

    def test_blank_is_refused(self):
        with self.assertRaises(UnknownSex):
            canonical_sex('  ')


if __name__ == '__main__':
    unittest.main()


class RangeCompleteness(unittest.TestCase):
    """`end` without `start` dropped the whole position filter.

    build_position_filter returns {} when start is None, so the query kept only
    the chromosome constraint and answered "is there anything on chr1 at all" —
    reported as an answer to a range question.
    """

    def test_end_without_start_is_refused(self):
        from beacon_api.query_semantics import IncompleteRange, require_complete_range
        with self.assertRaises(IncompleteRange):
            require_complete_range(start=None, end=5000)

    def test_start_alone_is_fine(self):
        from beacon_api.query_semantics import require_complete_range
        require_complete_range(start=1000, end=None)

    def test_both_supplied_is_fine(self):
        from beacon_api.query_semantics import require_complete_range
        require_complete_range(start=1000, end=5000)

    def test_neither_supplied_is_fine_it_is_simply_not_a_position_query(self):
        from beacon_api.query_semantics import require_complete_range
        require_complete_range(start=None, end=None)


class DatasetIdList(unittest.TestCase):
    """datasetIds is a list, but GET query strings collapse to single values.

    request.GET.dict() keeps one value per key, so a list can never be formed
    on GET and the parameter 400'd for every caller. Accept the comma-separated
    form, which is how a beacon client naturally writes it in a URL.
    """

    def test_a_comma_separated_string_becomes_a_list(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list('A,B'), ['A', 'B'])

    def test_a_single_value_becomes_a_one_element_list(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list('H3A_V6_AFR'), ['H3A_V6_AFR'])

    def test_a_real_list_passes_through(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list(['A', 'B']), ['A', 'B'])

    def test_whitespace_around_ids_is_stripped(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list(' A , B '), ['A', 'B'])

    def test_empty_entries_are_dropped_not_matched_as_blank_ids(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list('A,,B'), ['A', 'B'])

    def test_an_entirely_empty_value_yields_no_filter(self):
        from beacon_api.query_vocabulary import dataset_id_list
        self.assertEqual(dataset_id_list('  '), [])
        self.assertEqual(dataset_id_list(None), [])
