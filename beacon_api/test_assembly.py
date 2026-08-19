"""Regression tests for assembly-identifier canonicalisation.

The bug under test
------------------
``views_boolean`` applied the caller's ``assemblyId`` to Mongo as raw string
equality::

    mongo_query['assembly_id'] = validated_params['assemblyId']

while ``validators.validate_query_request`` blessed a flat whitelist of four
spellings — GRCh37, GRCh38, hg19, hg38 — with no alias table anywhere. hg38 and
GRCh38 name the *same* genome build, so a caller using UCSC vocabulary matched
nothing and received ``exists: false`` for a variant the panel holds.

A false negative is the one answer a discovery beacon must never give: it is
indistinguishable from a true one, and the GA4GH spec verifier cannot see it
(it checks envelope shape, and passed throughout the period when position
queries were off by one base).

Django-free by design, like test_query_semantics: no settings module, no
database, no network.

    python3 -m unittest beacon_api.test_assembly -v
"""
import unittest

from beacon_api.assembly import (
    UnknownAssembly,
    assembly_filter,
    assembly_query_values,
    canonical_assembly,
)


class CanonicalAssembly(unittest.TestCase):
    def test_ucsc_hg38_canonicalises_to_grch38(self):
        self.assertEqual(canonical_assembly('hg38'), 'GRCh38')

    def test_ucsc_hg19_canonicalises_to_grch37(self):
        self.assertEqual(canonical_assembly('hg19'), 'GRCh37')

    def test_grch_spellings_are_returned_unchanged(self):
        self.assertEqual(canonical_assembly('GRCh38'), 'GRCh38')
        self.assertEqual(canonical_assembly('GRCh37'), 'GRCh37')

    def test_matching_is_case_insensitive(self):
        for spelling in ('HG38', 'Hg38', 'grch38', 'GRCH38'):
            self.assertEqual(canonical_assembly(spelling), 'GRCh38', spelling)

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(canonical_assembly('  hg38 '), 'GRCh38')

    def test_an_unrecognised_assembly_is_refused_not_silently_dropped(self):
        with self.assertRaises(UnknownAssembly):
            canonical_assembly('GRCh99')

    def test_empty_and_none_are_refused(self):
        for value in ('', '   ', None):
            with self.assertRaises(UnknownAssembly):
                canonical_assembly(value)


class AssemblyQueryValues(unittest.TestCase):
    """The stored data may use either spelling depending on the ingest run,
    so a query must match both — the same treatment reference_name already
    gets at views_boolean.py:124."""

    def test_a_ucsc_query_also_matches_grch_stored_data(self):
        self.assertIn('GRCh38', assembly_query_values('hg38'))

    def test_a_grch_query_also_matches_ucsc_stored_data(self):
        self.assertIn('hg38', assembly_query_values('GRCh38'))

    def test_both_spellings_are_offered_for_every_known_build(self):
        self.assertEqual(sorted(assembly_query_values('hg19')), ['GRCh37', 'hg19'])
        self.assertEqual(sorted(assembly_query_values('GRCh38')), ['GRCh38', 'hg38'])

    def test_values_are_deduplicated_and_stable(self):
        values = assembly_query_values('hg38')
        self.assertEqual(len(values), len(set(values)))

    def test_an_unrecognised_assembly_is_refused(self):
        with self.assertRaises(UnknownAssembly):
            assembly_query_values('hg99')


class AssemblyFilter(unittest.TestCase):
    """The filter SHAPE is pinned here, not left to a one-line view edit.

    An equality filter is what produced the false negative; the fix is only
    real if the emitted key is the ``__in`` form.
    """

    def test_filter_uses_the_in_operator_not_equality(self):
        self.assertEqual(list(assembly_filter('hg38')), ['assembly_id__in'])

    def test_equality_key_is_never_emitted(self):
        self.assertNotIn('assembly_id', assembly_filter('GRCh38'))

    def test_filter_carries_both_spellings(self):
        self.assertEqual(
            sorted(assembly_filter('hg38')['assembly_id__in']),
            ['GRCh38', 'hg38'],
        )

    def test_an_unrecognised_assembly_is_refused(self):
        with self.assertRaises(UnknownAssembly):
            assembly_filter('GRCh99')


class RegressionContrast(unittest.TestCase):
    """Pinned so a revert to raw string equality goes red.

    Before the fix, the query value for 'hg38' was the single string 'hg38',
    which matched none of the GRCh38-labelled documents in the panel.
    """

    def test_hg38_does_not_collapse_to_the_bare_input(self):
        self.assertNotEqual(assembly_query_values('hg38'), ['hg38'])


if __name__ == '__main__':
    unittest.main()
