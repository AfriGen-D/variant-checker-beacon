"""
Regression tests for NoSQL operator injection and privacy disclosure control.

Standalone and MongoDB-free, following the pattern in
``beacon_api/test_query_semantics.py``: these exercise
``beacon_api.query_sanitizers`` and ``beacon_api.privacy``, neither of which
imports Django, DRF or MongoEngine, so they run with plain unittest and need
no settings module, no database and no network.

    python3 -m unittest beacon_api.test_query_injection -v

The bugs under test
-------------------
1. ``views_boolean.individual_query_boolean`` took ``request.data`` — arbitrary
   JSON on POST — and put the values straight into a Mongo query::

       mongo_query['diseases.diseaseCode'] = query_params['diseaseCode']
       exists = Individual.objects(__raw__=mongo_query).limit(1).count() > 0

   A body of ``{"diseaseCode": {"$regex": "^A"}}`` therefore reached MongoDB as
   a live operator, and the boolean ``exists`` answer became an oracle: an
   attacker binary-searches a stored disease code one character at a time by
   walking the anchored pattern. ``{"sex": {...}}`` additionally crashed on
   ``.upper()`` with a 500. The same shape existed across ``views.py``, where
   ``.filter(sex=query['sex'])`` passes a dict through to PyMongo unchanged.

2. Published allele frequencies were raw unrounded floats. An AF of exactly
   k/2N inverts to an exact carrier count — the Homer / Shringarpure-Bustamante
   beacon re-identification primitive.

3. Query logs stored the full client IP alongside the exact locus queried.
"""
import unittest

from beacon_api.privacy import (
    DEFAULT_AF_DECIMALS,
    DEFAULT_AF_MIN_PUBLISHED,
    anonymize_client_ip,
    publish_allele_frequency,
)
from beacon_api.query_sanitizers import (
    MAX_REGEX_TERM_LENGTH,
    MAX_TERM_LENGTH,
    UnsafeQueryValue,
    is_operator_key,
    reject_operator_keys,
    safe_regex_term,
    scalar_query_mapping,
    scalar_query_value,
)


def individual_mongo_query(body):
    """The query ``individual_query_boolean`` builds from a request body.

    Mirrors beacon_api/views_boolean.py::individual_query_boolean so the guard
    can be asserted without Django, DRF, or a live MongoDB. Raises
    UnsafeQueryValue exactly where the view returns its 400.
    """
    reject_operator_keys(body)
    sex = scalar_query_value(body.get('sex'), 'sex')
    disease_code = scalar_query_value(body.get('diseaseCode'), 'diseaseCode')

    query = {}
    if sex:
        sex = sex.upper()
        if sex in ('MALE', 'FEMALE', 'OTHER', 'UNKNOWN'):
            query['sex'] = sex
    if disease_code:
        query['diseases.diseaseCode'] = disease_code
    return query


class IndividualQueryInjectionTests(unittest.TestCase):
    """The exact payloads from the finding, end to end through the guard."""

    def test_dict_value_is_rejected(self):
        # The oracle payload: {"$regex": "^A"} would otherwise be executed.
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query({'diseaseCode': {'$regex': '^A'}})

    def test_dict_sex_is_rejected_and_does_not_raise_attributeerror(self):
        # Previously `query_params['sex'].upper()` -> AttributeError -> 500.
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query({'sex': {'$ne': None}})

    def test_list_value_is_rejected(self):
        # A list is how you smuggle an $in-style argument.
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query({'diseaseCode': ['A00', 'A01']})

    def test_operator_prefixed_key_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query({'$where': 'sleep(5000)'})

    def test_dotted_key_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query({'diseases.diseaseCode': 'A00'})

    def test_non_object_body_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            individual_mongo_query(['A00'])

    def test_normal_string_query_still_works(self):
        self.assertEqual(
            individual_mongo_query({'diseaseCode': 'MONDO:0005015'}),
            {'diseases.diseaseCode': 'MONDO:0005015'},
        )

    def test_normal_sex_query_still_works(self):
        self.assertEqual(individual_mongo_query({'sex': 'female'}), {'sex': 'FEMALE'})

    def test_both_parameters_together_still_work(self):
        self.assertEqual(
            individual_mongo_query({'sex': 'MALE', 'diseaseCode': 'A00'}),
            {'sex': 'MALE', 'diseases.diseaseCode': 'A00'},
        )

    def test_non_string_sex_does_not_raise(self):
        # A number is a legitimate JSON scalar. It must be handled, not crash,
        # and must not match a real sex value.
        self.assertEqual(individual_mongo_query({'sex': 1}), {})
        self.assertEqual(individual_mongo_query({'sex': True}), {})

    def test_unrecognised_sex_is_ignored_not_queried(self):
        self.assertEqual(individual_mongo_query({'sex': 'ROBOT'}), {})

    def test_empty_body_produces_no_filter(self):
        self.assertEqual(individual_mongo_query({}), {})

    def test_every_produced_key_is_a_literal_we_chose(self):
        # The guarantee that makes __raw__ safe: no caller input can occupy a
        # key position, so no value can be read as an operator.
        query = individual_mongo_query({'sex': 'FEMALE', 'diseaseCode': 'A00'})
        self.assertEqual(set(query), {'sex', 'diseases.diseaseCode'})
        for value in query.values():
            self.assertIsInstance(value, str)


class ScalarQueryValueTests(unittest.TestCase):

    def test_none_passes_through(self):
        self.assertIsNone(scalar_query_value(None, 'x'))

    def test_string_passes_through_unchanged(self):
        self.assertEqual(scalar_query_value('GRCh38', 'assemblyId'), 'GRCh38')

    def test_numbers_are_stringified(self):
        self.assertEqual(scalar_query_value(12345, 'start'), '12345')
        self.assertEqual(scalar_query_value(1.5, 'x'), '1.5')

    def test_booleans_are_stringified_not_left_as_ints(self):
        self.assertEqual(scalar_query_value(True, 'x'), 'true')
        self.assertEqual(scalar_query_value(False, 'x'), 'false')

    def test_structured_values_are_rejected(self):
        for bad in ({'$gt': 0}, ['a'], ('a',), {'a'}):
            with self.subTest(bad=bad):
                with self.assertRaises(UnsafeQueryValue):
                    scalar_query_value(bad, 'x')

    def test_overlong_value_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            scalar_query_value('A' * (MAX_TERM_LENGTH + 1), 'x')

    def test_value_at_the_limit_is_accepted(self):
        value = 'A' * MAX_TERM_LENGTH
        self.assertEqual(scalar_query_value(value, 'x'), value)

    def test_null_byte_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            scalar_query_value('A\x00B', 'x')

    def test_error_message_names_the_field(self):
        with self.assertRaises(UnsafeQueryValue) as ctx:
            scalar_query_value({'$regex': '^A'}, 'diseaseCode')
        self.assertIn('diseaseCode', str(ctx.exception))


class RegexTermTests(unittest.TestCase):
    """A substring match is a collection scan, so the term is capped harder."""

    def test_regex_term_cap_is_tighter_than_the_equality_cap(self):
        self.assertLess(MAX_REGEX_TERM_LENGTH, MAX_TERM_LENGTH)

    def test_term_longer_than_the_regex_cap_is_rejected(self):
        long_term = 'A' * (MAX_REGEX_TERM_LENGTH + 1)
        # Still fine as an indexed equality value...
        self.assertEqual(scalar_query_value(long_term, 'x'), long_term)
        # ...but not as an unindexed substring scan.
        with self.assertRaises(UnsafeQueryValue):
            safe_regex_term(long_term, 'label')

    def test_structured_regex_term_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            safe_regex_term({'$regex': '.*'}, 'label')

    def test_metacharacters_are_passed_through_for_the_odm_to_escape(self):
        # MongoEngine's StringField.prepare_query_value re.escape()s the value
        # for __contains/__icontains. We do not double-escape it here; the cap
        # above is what bounds the cost.
        self.assertEqual(safe_regex_term('(a+)+$', 'label'), '(a+)+$')


class OperatorKeyTests(unittest.TestCase):

    def test_dollar_prefixed_keys_are_operators(self):
        for key in ('$where', '$or', '$expr', '$regex'):
            with self.subTest(key=key):
                self.assertTrue(is_operator_key(key))

    def test_dotted_keys_are_paths(self):
        self.assertTrue(is_operator_key('diseases.diseaseCode'))

    def test_non_string_keys_are_rejected(self):
        self.assertTrue(is_operator_key(1))
        self.assertTrue(is_operator_key(None))

    def test_ordinary_keys_are_allowed(self):
        for key in ('sex', 'diseaseCode', 'assemblyId', 'referenceName'):
            with self.subTest(key=key):
                self.assertFalse(is_operator_key(key))

    def test_reject_operator_keys_rejects_non_mappings(self):
        for bad in ([], 'sex', None, 7):
            with self.subTest(bad=bad):
                with self.assertRaises(UnsafeQueryValue):
                    reject_operator_keys(bad)


class ScalarQueryMappingTests(unittest.TestCase):
    """The one-line guard applied at the top of each views.py POST handler."""

    def test_clean_mapping_is_returned_scalarised(self):
        self.assertEqual(
            scalar_query_mapping({'assemblyId': 'GRCh38', 'start': 1000}),
            {'assemblyId': 'GRCh38', 'start': '1000'},
        )

    def test_operator_value_anywhere_in_the_mapping_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            scalar_query_mapping({'assemblyId': 'GRCh38', 'sex': {'$ne': None}})

    def test_operator_key_anywhere_in_the_mapping_is_rejected(self):
        with self.assertRaises(UnsafeQueryValue):
            scalar_query_mapping({'$or': [{'sex': 'MALE'}]})

    def test_it_does_not_mutate_the_caller_mapping(self):
        original = {'start': 1000}
        scalar_query_mapping(original)
        self.assertEqual(original, {'start': 1000})


class AlleleFrequencyDisclosureTests(unittest.TestCase):
    """Rounding + small-cell suppression on the published AF."""

    # AfriGen-D V6HC-S_AFR: 1,895 samples -> 3,790 alleles.
    PANEL_ALLELES = 3790

    def test_a_single_carrier_allele_is_suppressed(self):
        # The exact re-identification primitive: AF == 1/2N -> carrier count 1.
        singleton = 1 / self.PANEL_ALLELES
        self.assertIsNone(publish_allele_frequency(singleton))

    def test_frequencies_below_the_floor_are_suppressed(self):
        self.assertIsNone(publish_allele_frequency(DEFAULT_AF_MIN_PUBLISHED / 2))

    def test_the_floor_itself_is_published(self):
        self.assertIsNotNone(publish_allele_frequency(DEFAULT_AF_MIN_PUBLISHED))

    def test_published_value_is_rounded_to_the_configured_precision(self):
        self.assertEqual(publish_allele_frequency(0.123456789), 0.123)

    def test_rounding_grid_is_coarser_than_one_allele(self):
        # The property that stops inversion: two AFs one allele apart must
        # collapse onto the same published value.
        base = 0.5
        one_allele_more = base + 1 / self.PANEL_ALLELES
        self.assertEqual(
            publish_allele_frequency(base),
            publish_allele_frequency(one_allele_more),
        )

    def test_grid_step_exceeds_one_over_two_n(self):
        self.assertGreater(10 ** -DEFAULT_AF_DECIMALS, 1 / self.PANEL_ALLELES)

    def test_near_fixation_collapses_to_one(self):
        # AF == 1 - 1/2N pins a single NON-carrier; rounding must hide it.
        self.assertEqual(
            publish_allele_frequency(1 - 1 / self.PANEL_ALLELES),
            publish_allele_frequency(1.0),
        )

    def test_absent_and_degenerate_frequencies_publish_nothing(self):
        for value in (None, 0, 0.0, -0.1, True, False, '0.5'):
            with self.subTest(value=value):
                self.assertIsNone(publish_allele_frequency(value))

    def test_precision_and_floor_are_overridable(self):
        self.assertEqual(
            publish_allele_frequency(0.123456, decimals=1, min_frequency=0.05),
            0.1,
        )
        self.assertIsNone(
            publish_allele_frequency(0.02, decimals=1, min_frequency=0.05)
        )

    def test_defaults_are_sane(self):
        self.assertGreater(DEFAULT_AF_DECIMALS, 0)
        self.assertGreater(DEFAULT_AF_MIN_PUBLISHED, 0)
        self.assertLess(DEFAULT_AF_MIN_PUBLISHED, 1)


class ClientIpAnonymisationTests(unittest.TestCase):
    """The stored value must not be a direct identifier, but must still group."""

    def test_ipv4_is_truncated_to_the_network(self):
        self.assertEqual(anonymize_client_ip('196.21.218.147'), '196.21.218.0/24')

    def test_ipv4_hosts_on_one_network_collapse_together(self):
        self.assertEqual(
            anonymize_client_ip('196.21.218.1'),
            anonymize_client_ip('196.21.218.254'),
        )

    def test_different_networks_stay_distinguishable(self):
        # Distinct-client counting still works at network granularity.
        self.assertNotEqual(
            anonymize_client_ip('196.21.218.1'),
            anonymize_client_ip('196.21.219.1'),
        )

    def test_the_full_address_never_survives(self):
        for ip in ('196.21.218.147', '2001:db8:abcd:1234::1', '10.0.0.5'):
            with self.subTest(ip=ip):
                self.assertNotEqual(anonymize_client_ip(ip), ip)

    def test_ipv6_is_truncated_to_a_48(self):
        self.assertEqual(
            anonymize_client_ip('2001:db8:abcd:1234::1'), '2001:db8:abcd::/48'
        )

    def test_ipv6_loopback_has_nothing_left_to_keep(self):
        self.assertEqual(anonymize_client_ip('::1'), '::/48')

    def test_unparseable_input_yields_empty_not_the_original(self):
        for value in ('', '   ', None, 'not-an-ip', '1.2.3', '1.2.3.999', 42):
            with self.subTest(value=value):
                self.assertEqual(anonymize_client_ip(value), '')

    def test_result_fits_the_querylog_field(self):
        # QueryLog.client_ip is StringField(max_length=64).
        self.assertLessEqual(
            len(anonymize_client_ip('2001:0db8:abcd:1234:5678:9abc:def0:1234')), 64
        )


if __name__ == '__main__':
    unittest.main()
