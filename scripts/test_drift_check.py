"""
Tests for the release-drift classifier.

Standalone: ``drift_check.classify`` does no I/O, so these run with plain
unittest and need no network, settings or database.

    python3 -m unittest scripts.test_drift_check -v
"""
import unittest

from scripts.drift_check import CURRENT, PREDATES_MARKER, STALE, THROTTLED, UNKNOWN, classify


class ClassifyTests(unittest.TestCase):
    def test_matching_release_is_current(self):
        self.assertEqual(classify({"ok": True, "release": "v1.1.7"}, "v1.1.7"), CURRENT)

    def test_older_release_is_stale(self):
        self.assertEqual(classify({"ok": True, "release": "v1.1.4"}, "v1.1.7"), STALE)

    def test_unreachable_is_unknown_never_current(self):
        # A transport failure and a healthy instance must not look alike.
        self.assertEqual(classify({"ok": False, "status": 0}, "v1.1.7"), UNKNOWN)

    def test_429_is_throttled_not_offline(self):
        # The ARDI case: the beacon answered, it declined to serve. That is a
        # different fact from being down, and mirrors how the aggregator's own
        # health checker treats it.
        self.assertEqual(classify({"ok": False, "status": 429}, "v1.1.7"), THROTTLED)

    def test_release_absent_predates_the_marker(self):
        # An image built before the release marker shipped. Not stale-by-tag —
        # unmeasurable, and it must not be reported as up to date.
        self.assertEqual(classify({"ok": True}, "v1.1.7"), PREDATES_MARKER)

    def test_release_unknown_predates_or_unstamped(self):
        self.assertEqual(classify({"ok": True, "release": "unknown"}, "v1.1.7"), PREDATES_MARKER)

    def test_release_ahead_of_the_tag_is_not_current(self):
        # An instance reporting a release the repo does not have is a real
        # signal (hand-deployed, or a tag was deleted), not something to
        # silently pass.
        self.assertEqual(classify({"ok": True, "release": "v9.9.9"}, "v1.1.7"), STALE)

    def test_500_is_unknown_not_stale(self):
        self.assertEqual(classify({"ok": False, "status": 500}, "v1.1.7"), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
