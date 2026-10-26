"""Tests for the HGVS g. substitution parser (G7b). Plain unittest, no Django."""
import unittest

from beacon_api.hgvs import HgvsError, parse_genomic_allele_short_form


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


if __name__ == '__main__':
    unittest.main()
