"""Regression tests for rejecting query parameters this beacon cannot honour.

Django-free, like ``test_pagination_filters``:

    python3 -m unittest beacon_api.test_unsupported_params -v

The bug under test (review 2026-10-22, G1): ``BeaconQuerySerializer`` has no
``geneId`` field, DRF drops unknown fields, and ``geneId=NOSUCHGENE_ZZZ`` was
answered ``exists: true`` over the whole panel. The same held for
``aminoacidChanges``, ``variantMinLength``, ``variantMaxLength``, array-valued
``start``/``end`` and any misspelt parameter name.
"""
import unittest

from beacon_api.unsupported_params import (
    INDIVIDUAL_IMPLEMENTED,
    UnsupportedParameters,
    reject_unsupported_params,
)

VALID_LOCUS = {
    'referenceName': '11', 'start': '5227001', 'assemblyId': 'GRCh38',
}


class RejectedParameterTests(unittest.TestCase):
    def assertRejects(self, params, *needles):
        with self.assertRaises(UnsupportedParameters) as ctx:
            reject_unsupported_params(params)
        for needle in needles:
            self.assertIn(needle, str(ctx.exception))

    def test_gene_id_is_rejected_not_dropped(self):
        self.assertRejects({**VALID_LOCUS, 'geneId': 'HBB'}, 'geneId')

    def test_gene_id_of_a_nonexistent_gene_is_rejected_the_same_way(self):
        self.assertRejects({'assemblyId': 'GRCh38', 'geneId': 'NOSUCHGENE_ZZZ'}, 'geneId')

    def test_each_advertised_but_unimplemented_parameter_is_rejected(self):
        for name in ('aminoacidChanges', 'variantMinLength', 'variantMaxLength'):
            with self.subTest(name=name):
                self.assertRejects({**VALID_LOCUS, name: '10'}, name)

    def test_array_start_and_end_are_rejected(self):
        self.assertRejects({'referenceName': '17', 'start': [5000000, 7676592]}, 'start')
        self.assertRejects({'referenceName': '17', 'start': 5, 'end': [7, 9]}, 'end')

    def test_an_unknown_parameter_is_rejected_because_it_may_be_a_misspelt_filter(self):
        self.assertRejects({**VALID_LOCUS, 'bogusParam': 'zzz'}, 'bogusParam')

    def test_every_offender_is_named(self):
        self.assertRejects({**VALID_LOCUS, 'geneId': 'HBB', 'bogusParam': '1'},
                           'geneId', 'bogusParam')

    def test_an_empty_value_is_still_rejected(self):
        # geneId= (blank) narrows nothing today, but the caller meant to
        # narrow; telling them is cheaper than a silent whole-panel answer.
        self.assertRejects({**VALID_LOCUS, 'geneId': ''}, 'geneId')

    def test_echoed_names_are_bounded(self):
        with self.assertRaises(UnsupportedParameters) as ctx:
            reject_unsupported_params({f'x{i}' * 40: 1 for i in range(50)})
        self.assertLess(len(str(ctx.exception)), 1500)


class AcceptedParameterTests(unittest.TestCase):
    def test_a_valid_locus_passes(self):
        reject_unsupported_params(dict(VALID_LOCUS))

    def test_every_serializer_field_passes(self):
        reject_unsupported_params({
            'referenceName': '1', 'chromosome': '1', 'start': 1, 'end': 2,
            'position': 1, 'referenceBases': 'A', 'alternateBases': 'T',
            'variantType': 'SNP', 'assemblyId': 'GRCh38',
            'datasetIds': ['H3A_V6_AFR'], 'requestedGranularity': 'boolean',
            'skip': 0, 'limit': 10,
        })

    def test_envelope_keys_the_network_sends_pass(self):
        reject_unsupported_params({
            **VALID_LOCUS, 'includeResultsetResponses': 'ALL', '_t': '1', 'testMode': 'false',
            'requestedSchemas': [], 'pagination': {'skip': 0, 'limit': 1},
        })

    def test_filters_is_left_to_its_own_rejection(self):
        # filters has a dedicated, clearer message in beacon_api/filters.py.
        reject_unsupported_params({**VALID_LOCUS, 'filters': ''})

    def test_non_mapping_input_is_not_this_modules_problem(self):
        reject_unsupported_params(None)
        reject_unsupported_params([])


class IndividualEndpointTests(unittest.TestCase):
    """individual_query_boolean reads only sex and diseaseCode; everything
    else was dropped and answered over all individuals."""

    def test_sex_and_disease_code_pass(self):
        reject_unsupported_params({'sex': 'MALE', 'diseaseCode': 'X', 'limit': 1},
                                  allowed=INDIVIDUAL_IMPLEMENTED)

    def test_a_variant_parameter_is_rejected_here(self):
        with self.assertRaises(UnsupportedParameters) as ctx:
            reject_unsupported_params({'sex': 'MALE', 'geneId': 'HBB'},
                                      allowed=INDIVIDUAL_IMPLEMENTED)
        self.assertIn('geneId', str(ctx.exception))

    def test_a_locus_parameter_is_rejected_here(self):
        with self.assertRaises(UnsupportedParameters):
            reject_unsupported_params({'referenceName': '1'},
                                      allowed=INDIVIDUAL_IMPLEMENTED)

    def test_the_message_lists_this_endpoints_own_parameters(self):
        with self.assertRaises(UnsupportedParameters) as ctx:
            reject_unsupported_params({'ethnicity': 'x'}, allowed=INDIVIDUAL_IMPLEMENTED)
        self.assertIn('diseaseCode', str(ctx.exception))
        self.assertNotIn('referenceBases', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
