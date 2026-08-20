"""
Tests for the build-time release stamp.

Standalone: ``beacon_api.release`` imports no Django, DRF or MongoEngine, so
these run with plain unittest and need no settings module, database or network.

    python3 -m unittest beacon_api.test_release -v
"""
import unittest

from beacon_api.release import UNKNOWN_RELEASE, get_release


class GetReleaseTests(unittest.TestCase):
    def test_reports_the_stamped_release(self):
        self.assertEqual(get_release({'BEACON_RELEASE': 'v1.1.5'}), 'v1.1.5')

    def test_unset_reports_unknown(self):
        self.assertEqual(get_release({}), UNKNOWN_RELEASE)

    def test_empty_reports_unknown(self):
        # `ARG BEACON_RELEASE=""` that is declared but never passed expands to
        # the empty string, not to an unset variable.
        self.assertEqual(get_release({'BEACON_RELEASE': ''}), UNKNOWN_RELEASE)

    def test_whitespace_only_reports_unknown(self):
        self.assertEqual(get_release({'BEACON_RELEASE': '  \n'}), UNKNOWN_RELEASE)

    def test_strips_surrounding_whitespace(self):
        # A YAML block-scalar build-arg carries a trailing newline into the
        # environment; reporting 'v1.1.5\n' would fail an equality check
        # against the requested version in the upgrade script.
        self.assertEqual(get_release({'BEACON_RELEASE': ' v1.1.5\n'}), 'v1.1.5')

    def test_unknown_is_the_literal_string_unknown(self):
        # The drift check distinguishes "stale" from "predates the marker" by
        # this exact value; renaming it silently breaks that branch.
        self.assertEqual(UNKNOWN_RELEASE, 'unknown')


if __name__ == '__main__':
    unittest.main()
