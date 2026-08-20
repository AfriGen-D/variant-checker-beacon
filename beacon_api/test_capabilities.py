"""Regression tests: an unimplemented endpoint must not answer "no".

The defect
----------
``/datasets/{id}/{entry_type}`` and the ``/individuals`` list both returned a
constant empty query envelope for every input — HTTP 200, ``exists: false``.
A dataset the catalogue reports as holding 42 million variants answered
"not found" for a locus inside it.

The view directly above the dataset-scoped stub carries a comment recording
why that is dangerous: returning the empty 200 envelope "made a MongoDB outage
indistinguishable from a genuine miss, so clients (and the Beacon Network
aggregator) would record an authoritative 'does not exist' for data we simply
could not read". The stub below it did exactly that, by construction.

Django-free, like query_semantics / assembly / query_vocabulary.

    python3 -m unittest beacon_api.test_capabilities -v
"""
import unittest

from beacon_api.capabilities import (
    DATASET_SCOPED_ENTRY_TYPES,
    is_assembly_served,
    is_dataset_scope_supported,
    served_assemblies,
    unserved_assembly_message,
    unsupported_dataset_scope_message,
)


class DatasetScopeSupport(unittest.TestCase):
    def test_nothing_is_dataset_scoped_yet(self):
        """Boolean mode implements no per-dataset drill-down today.

        If that changes, add the entry type to DATASET_SCOPED_ENTRY_TYPES in
        the same commit that implements it — not before, or this beacon starts
        answering 'no' for it again.
        """
        self.assertEqual(DATASET_SCOPED_ENTRY_TYPES, frozenset())

    def test_an_unimplemented_entry_type_is_not_supported(self):
        for et in ('g_variants', 'individuals', 'biosamples', 'analyses', 'runs'):
            self.assertFalse(is_dataset_scope_supported(et), et)

    def test_support_is_driven_by_the_set_not_hardcoded(self):
        self.assertTrue(is_dataset_scope_supported('g_variants',
                                                   supported=frozenset({'g_variants'})))


class UnsupportedMessage(unittest.TestCase):
    """The message must say the beacon cannot answer — never imply absence."""

    def setUp(self):
        self.msg = unsupported_dataset_scope_message('H3A_V6_AFR', 'g_variants')

    def test_it_names_the_entry_type(self):
        self.assertIn('g_variants', self.msg)

    def test_it_names_the_dataset(self):
        self.assertIn('H3A_V6_AFR', self.msg)

    def test_it_does_not_claim_the_data_is_absent(self):
        lowered = self.msg.lower()
        for forbidden in ('not found', 'no match', 'does not exist', 'no results'):
            self.assertNotIn(forbidden, lowered)

    def test_it_points_the_caller_at_the_endpoint_that_works(self):
        self.assertIn('/api/g_variants', self.msg)


if __name__ == '__main__':
    unittest.main()


class ServedAssemblyTests(unittest.TestCase):
    """
    The beacon holds only GRCh38. GRCh37 and hg19 are *known* assemblies, so
    they pass validation, canonicalise correctly, and then match no stored
    data — answering `exists: false` rather than refusing.

    That is the same defect capabilities.py was created for: "I cannot answer"
    and "the answer is no" are different statements, and only one is true.
    """

    def test_served_assemblies_comes_from_the_datasets(self):
        # Self-maintaining: load a GRCh37 dataset and the beacon starts
        # answering for it, with no code change.
        self.assertEqual(served_assemblies(["GRCh38"]), frozenset({"GRCh38"}))

    def test_served_assemblies_canonicalises_and_dedupes(self):
        self.assertEqual(served_assemblies(["hg38", "GRCh38"]), frozenset({"GRCh38"}))

    def test_served_assemblies_ignores_blank_declarations(self):
        self.assertEqual(served_assemblies(["GRCh38", None, ""]), frozenset({"GRCh38"}))

    def test_a_held_assembly_is_served(self):
        self.assertTrue(is_assembly_served("GRCh38", frozenset({"GRCh38"})))

    def test_a_synonym_of_a_held_assembly_is_served(self):
        # hg38 must not be refused just because the dataset spells it GRCh38.
        self.assertTrue(is_assembly_served("hg38", frozenset({"GRCh38"})))

    def test_a_known_but_unheld_assembly_is_not_served(self):
        self.assertFalse(is_assembly_served("GRCh37", frozenset({"GRCh38"})))
        self.assertFalse(is_assembly_served("hg19", frozenset({"GRCh38"})))

    def test_no_datasets_means_nothing_is_served(self):
        # An empty catalogue must not accidentally serve everything.
        self.assertFalse(is_assembly_served("GRCh38", frozenset()))

    def test_message_says_cannot_answer_not_absent(self):
        msg = unserved_assembly_message("GRCh37", frozenset({"GRCh38"}))
        self.assertIn("GRCh37", msg)
        self.assertIn("GRCh38", msg)
        low = msg.lower()
        self.assertIn("cannot answer", low)
        # It must never imply the variant is absent — that is the bug.
        self.assertNotIn("not found", low)
        self.assertNotIn("does not exist", low)
