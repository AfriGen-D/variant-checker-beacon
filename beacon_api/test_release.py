"""
Tests for the build-time release stamp.

Standalone: ``beacon_api.release`` imports no Django, DRF or MongoEngine, so
these run with plain unittest and need no settings module, database or network.

    python3 -m unittest beacon_api.test_release -v
"""
import unittest

from beacon_api.release import UNKNOWN_RELEASE, cache_key_prefix, get_release


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


class CacheKeyPrefixTests(unittest.TestCase):
    """A new release must not be served the previous release's cached answers
    (TASKS G6: ``cache_page`` held a pre-deploy 200 YES for 5 minutes)."""

    def test_two_releases_never_share_a_prefix(self):
        a = cache_key_prefix('beacon_boolean', {'BEACON_RELEASE': 'v1.1.12'})
        b = cache_key_prefix('beacon_boolean', {'BEACON_RELEASE': 'v1.1.13'})
        self.assertNotEqual(a, b)

    def test_prefix_carries_the_base_and_the_release(self):
        self.assertEqual(
            cache_key_prefix('beacon_boolean', {'BEACON_RELEASE': 'v1.1.13'}),
            'beacon_boolean:v1.1.13',
        )

    def test_unstamped_image_still_gets_a_stable_prefix(self):
        self.assertEqual(
            cache_key_prefix('beacon_boolean', {}), 'beacon_boolean:unknown'
        )

    def test_unsafe_characters_cannot_reach_the_cache_key(self):
        p = cache_key_prefix('beacon_boolean', {'BEACON_RELEASE': 'v1 .1\n/x*'})
        self.assertRegex(p, r'^[A-Za-z0-9_.:-]+$')


if __name__ == '__main__':
    unittest.main()
