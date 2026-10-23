"""validate_query_request must refuse parameters it would otherwise drop.

Needs Django + DRF (validators.py imports them):

    python3 -m unittest beacon_api.test_unsupported_params_validate -v
"""
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth'],
        DATABASES={},
        USE_TZ=True,
    )
    django.setup()

import unittest  # noqa: E402

from rest_framework.exceptions import ValidationError  # noqa: E402

from beacon_api.validators import validate_query_request  # noqa: E402

LOCUS = {'referenceName': '11', 'start': '5227001', 'assemblyId': 'GRCh38'}


class ValidateRejectsDroppedParametersTests(unittest.TestCase):
    def test_gene_id_raises_a_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_query_request({'assemblyId': 'GRCh38', 'geneId': 'NOSUCHGENE_ZZZ'})
        self.assertIn('geneId', str(ctx.exception.detail))

    def test_bogus_parameter_on_a_valid_locus_raises(self):
        with self.assertRaises(ValidationError):
            validate_query_request({**LOCUS, 'bogusParam': 'zzz'})

    def test_array_start_in_a_post_body_raises(self):
        with self.assertRaises(ValidationError):
            validate_query_request({'referenceName': '17', 'start': [1, 2]})

    def test_comma_separated_start_still_raises(self):
        with self.assertRaises(ValidationError):
            validate_query_request({'referenceName': '17', 'start': '5000000,7676592'})

    def test_valid_locus_still_validates(self):
        out = validate_query_request(dict(LOCUS))
        self.assertEqual(out['referenceName'], '11')
        self.assertEqual(out['start'], 5227001)

    def test_envelope_keys_do_not_break_a_valid_locus(self):
        out = validate_query_request({**LOCUS, 'includeResultsetResponses': 'ALL', '_t': '17'})
        self.assertEqual(out['assemblyId'], 'GRCh38')


if __name__ == '__main__':
    unittest.main()
