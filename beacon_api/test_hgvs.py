"""Tests for the HGVS g. substitution parser (G7b). Plain unittest, no Django."""
import unittest

from beacon_api.hgvs import (
    HgvsError, expand_genomic_allele_short_form, parse_genomic_allele_short_form,
)


class ParseTests(unittest.TestCase):
    def test_rs334_grch38_is_converted_to_the_stored_zero_based_start(self):
        # Known positive: production answers true at 11:5227001 (0-based).
        self.assertEqual(
            parse_genomic_allele_short_form('NC_000011.10:g.5227002T>A'),
            {'assemblyId': 'GRCh38', 'referenceName': '11',
             'start': 5227001, 'referenceBases': 'T', 'alternateBases': 'A'},
        )

    def test_grch37_accession_version_maps_to_grch37(self):
        got = parse_genomic_allele_short_form('NC_000011.9:g.5248232T>A')
        self.assertEqual(got['assemblyId'], 'GRCh37')
        self.assertEqual(got['start'], 5248231)

    def test_x_and_y_accessions(self):
        self.assertEqual(parse_genomic_allele_short_form('NC_000023.11:g.100C>G')['referenceName'], 'X')
        self.assertEqual(parse_genomic_allele_short_form('NC_000024.10:g.100C>G')['referenceName'], 'Y')

    def test_position_one_is_the_lowest_valid_and_becomes_zero(self):
        self.assertEqual(parse_genomic_allele_short_form('NC_000001.11:g.1A>C')['start'], 0)

    def test_position_zero_is_refused(self):
        with self.assertRaises(HgvsError):
            parse_genomic_allele_short_form('NC_000001.11:g.0A>C')

    def test_unknown_accession_version_is_refused_not_guessed(self):
        for bad in ('NC_000011.8:g.5227002T>A', 'NC_000025.1:g.1A>C', 'NM_000518.5:c.20A>T'):
            with self.subTest(bad=bad), self.assertRaises(HgvsError):
                parse_genomic_allele_short_form(bad)

    def test_non_substitutions_are_refused(self):
        for bad in ('NC_000011.10:g.5227002del', 'NC_000011.10:g.5227002_5227003insA',
                    'NC_000011.10:g.5227002T=', 'NC_000011.10:g.5227002T>T'):
            with self.subTest(bad=bad), self.assertRaises(HgvsError):
                parse_genomic_allele_short_form(bad)

    def test_empty_and_wrong_type(self):
        for bad in ('', None, 5227002, '  '):
            with self.subTest(bad=bad), self.assertRaises(HgvsError):
                parse_genomic_allele_short_form(bad)

    def test_lowercase_bases_are_normalised(self):
        got = parse_genomic_allele_short_form('NC_000011.10:g.5227002t>a')
        self.assertEqual((got['referenceBases'], got['alternateBases']), ('T', 'A'))



class ExpandTests(unittest.TestCase):
    def test_absent_key_returns_params_unchanged(self):
        params = {'referenceName': '11', 'start': '5227001'}
        self.assertEqual(expand_genomic_allele_short_form(params), params)

    def test_key_is_replaced_by_explicit_fields(self):
        got = expand_genomic_allele_short_form(
            {'genomicAlleleShortForm': 'NC_000011.10:g.5227002T>A', 'limit': '1'})
        self.assertEqual(got, {
            'limit': '1', 'assemblyId': 'GRCh38', 'referenceName': '11',
            'start': '5227001', 'referenceBases': 'T', 'alternateBases': 'A'})

    def test_input_dict_is_not_mutated(self):
        params = {'genomicAlleleShortForm': 'NC_000011.10:g.5227002T>A'}
        expand_genomic_allele_short_form(params)
        self.assertEqual(params, {'genomicAlleleShortForm': 'NC_000011.10:g.5227002T>A'})

    def test_mixing_with_explicit_locus_fields_is_refused(self):
        for extra in ({'referenceName': '11'}, {'start': '5227001'}, {'alternateBases': 'A'},
                      {'chromosome': '11'}, {'position': '5227001'}, {'end': '5227002'}):
            with self.subTest(extra=extra), self.assertRaises(HgvsError):
                expand_genomic_allele_short_form(
                    {'genomicAlleleShortForm': 'NC_000011.10:g.5227002T>A', **extra})

    def test_matching_assembly_is_allowed_and_a_conflicting_one_refused(self):
        hgvs = 'NC_000011.10:g.5227002T>A'
        self.assertEqual(expand_genomic_allele_short_form(
            {'genomicAlleleShortForm': hgvs, 'assemblyId': 'GRCh38'})['assemblyId'], 'GRCh38')
        with self.assertRaises(HgvsError):
            expand_genomic_allele_short_form({'genomicAlleleShortForm': hgvs, 'assemblyId': 'GRCh37'})

    def test_a_list_value_is_refused(self):
        with self.assertRaises(HgvsError):
            expand_genomic_allele_short_form({'genomicAlleleShortForm': ['NC_000011.10:g.5227002T>A']})


if __name__ == '__main__':
    unittest.main()
