"""
Repository hygiene: nothing that only exists on one developer's machine may be
tracked.

Standalone: stdlib only, no Django, settings module, database or network.

    python3 -m unittest beacon_api.test_repo_hygiene -v

Why this exists. Ten symlinks were committed in #16 -- ``afrigend-beacon2-tools/.venv``
and nine ``__pycache__`` entries -- each pointing at an absolute path under
``/Users/<developer>/...nosync`` (the macOS convention for keeping a directory out
of a synced folder). On any other machine they dangle. A cluster user who cloned
the repo and ran ``python3 -m venv .venv`` got ``File exists`` and no usable
environment, because the clone shipped a ``.venv`` that pointed nowhere.

``.gitignore`` already listed ``__pycache__/`` and ``venv/``. Both patterns end in a
slash, which matches only a directory, so a *symlink* with the same name was never
ignored and a plain ``git add -A`` picked it up. This test is the detector for that
shape; the ``.gitignore`` patterns are the fix for the cause.
"""

import os
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JUNK_DIR_NAMES = {"__pycache__", ".venv", "venv"}
JUNK_SUFFIXES = (".nosync",)


def escapes_repo(repo_root, tracked_path, target):
    """True if a symlink at ``tracked_path`` pointing to ``target`` would leave the repo.

    An absolute target always escapes: it names a location on the machine that
    committed it. A relative target escapes only if, resolved against the link's
    own directory, it lands outside ``repo_root``.
    """
    if os.path.isabs(target):
        return True
    resolved = os.path.normpath(
        os.path.join(repo_root, os.path.dirname(tracked_path), target)
    )
    return not (resolved == repo_root or resolved.startswith(repo_root + os.sep))


def is_machine_local_artifact(tracked_path):
    """True for a path that is a per-machine build or environment artifact."""
    parts = tracked_path.split("/")
    return any(part in JUNK_DIR_NAMES for part in parts) or any(
        part.endswith(JUNK_SUFFIXES) for part in parts
    )


def tracked_entries():
    """Yield ``(mode, path)`` for every tracked entry, from the index."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "-s"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for entry in out.split("\0"):
        if not entry:
            continue
        meta, name = entry.split("\t", 1)
        yield meta.split()[0], name


class EscapesRepoTests(unittest.TestCase):
    """The classifier, on synthetic inputs, so a regression cannot hide in git state."""

    ROOT = os.path.join(os.sep, "work", "repo")

    def test_absolute_target_escapes(self):
        self.assertTrue(
            escapes_repo(
                self.ROOT, "tools/.venv", "/Users/someone/repo/tools/.venv.nosync"
            )
        )

    def test_absolute_target_escapes_even_if_it_points_inside_this_checkout(self):
        # It names a path on the committing machine; on another machine the same
        # string is a different location, which is the whole defect.
        self.assertTrue(
            escapes_repo(
                self.ROOT, "tools/link", os.path.join(self.ROOT, "tools", "real")
            )
        )

    def test_relative_target_inside_the_repo_is_fine(self):
        self.assertFalse(escapes_repo(self.ROOT, "tools/link", "real"))

    def test_dotdot_that_stays_inside_the_repo_is_fine(self):
        self.assertFalse(escapes_repo(self.ROOT, "a/b/link", "../c"))

    def test_dotdot_that_reaches_the_repo_root_is_fine(self):
        self.assertFalse(escapes_repo(self.ROOT, "a/link", ".."))

    def test_dotdot_that_leaves_the_repo_escapes(self):
        self.assertTrue(escapes_repo(self.ROOT, "a/link", "../../outside"))

    def test_sibling_directory_with_a_shared_prefix_escapes(self):
        # /work/repo-other must not be mistaken for /work/repo/... by a bare
        # startswith() on the root.
        self.assertTrue(escapes_repo(self.ROOT, "link", "../repo-other/file"))


class IsMachineLocalArtifactTests(unittest.TestCase):
    def test_flags_each_junk_shape(self):
        for path in (
            "tools/.venv",
            "tools/venv/bin/python",
            "tools/pkg/__pycache__/x.pyc",
            "tools/.venv.nosync",
            "tools/__pycache__.nosync/x",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_machine_local_artifact(path))

    def test_does_not_flag_ordinary_paths(self):
        for path in (
            "tools/venv_helper.py",
            "docs/venv-guide.md",
            "tools/pkg/cache.py",
            "README.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_machine_local_artifact(path))


@unittest.skipUnless(
    os.path.exists(os.path.join(REPO, ".git")),
    "not a git checkout; nothing tracked to inspect",
)
class TrackedTreeTests(unittest.TestCase):
    """The real index. These are the two tests that fail on the pre-fix tree."""

    def test_no_tracked_symlink_leaves_the_repository(self):
        escaping = []
        for mode, name in tracked_entries():
            if mode != "120000":
                continue
            target = os.readlink(os.path.join(REPO, name))
            if escapes_repo(REPO, name, target):
                escaping.append("%s -> %s" % (name, target))
        self.assertEqual(
            escaping,
            [],
            "tracked symlinks that point outside the repository (they dangle on "
            "every other machine):\n  " + "\n  ".join(escaping),
        )

    def test_no_machine_local_artifact_is_tracked(self):
        tracked = [
            name for _, name in tracked_entries() if is_machine_local_artifact(name)
        ]
        self.assertEqual(
            tracked,
            [],
            "per-machine build or environment artifacts are tracked; delete them "
            "with `git rm` and extend .gitignore:\n  " + "\n  ".join(tracked),
        )


if __name__ == "__main__":
    unittest.main()
