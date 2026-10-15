"""Tests for the allele-frequency extraction gate (validation/validate_af_extraction.py)."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# CI's test environment has no cyvcf2. The transformer only needs the name to be
# importable here (the counting tests use fake variants), so stand one in rather than
# depend on another test module having done it first.
try:
    import cyvcf2  # noqa: F401
except ImportError:
    sys.modules["cyvcf2"] = MagicMock()

from validation.validate_af_extraction import count_allele_frequencies  # noqa: E402


class FakeVariant:
    """Just enough of a cyvcf2 Variant: CHROM, POS, REF, ALT and INFO.get()."""

    def __init__(self, af, alt=("T",), pos=100, info_present=True):
        self.CHROM, self.POS, self.REF, self.ALT = "22", pos, "A", list(alt)
        self.INFO = _Info({} if af is _MISSING else {"AF": af}) if info_present else None


_MISSING = object()


class _Info(dict):
    """cyvcf2's INFO returns None for a missing key."""


def v(af, **kw):
    return FakeVariant(af, **kw)


class TestCounting:
    def test_every_record_with_af_passes(self):
        r = count_allele_frequencies([v(0.1), v(0.5), v(0.25)], limit=10)
        assert (r["checked"], r["with_af"]) == (3, 3)

    def test_a_record_without_af_is_counted_as_missing(self):
        r = count_allele_frequencies([v(0.1), v(_MISSING), v(0.5)], limit=10)
        assert (r["checked"], r["with_af"]) == (3, 2)

    def test_af_given_as_a_one_element_tuple_counts(self):
        # cyvcf2 returns a tuple for a Number=A field; this is the case the fix was for.
        assert count_allele_frequencies([v((0.3,))], limit=10)["with_af"] == 1

    def test_a_multiallelic_site_needs_an_af_for_every_alt(self):
        # Two ALTs but one AF value: the second allele has no frequency, so the
        # record must NOT count as having one. Checking only the first value hides this.
        r = count_allele_frequencies([v((0.2,), alt=("T", "G"))], limit=10)
        assert (r["checked"], r["with_af"]) == (1, 0)

    def test_a_multiallelic_site_with_an_af_per_alt_counts(self):
        r = count_allele_frequencies([v((0.2, 0.1), alt=("T", "G"))], limit=10)
        assert r["with_af"] == 1

    def test_a_variant_without_an_info_object_counts_as_missing_not_a_crash(self):
        r = count_allele_frequencies([v(0.1, info_present=False)], limit=10)
        assert (r["checked"], r["with_af"]) == (1, 0)

    def test_an_unparseable_af_counts_as_missing(self):
        assert count_allele_frequencies([v("not-a-number")], limit=10)["with_af"] == 0

    def test_a_monomorphic_site_with_no_alt_is_checked_against_one_slot(self):
        r = count_allele_frequencies([v(0.0, alt=())], limit=10)
        assert (r["checked"], r["with_af"]) == (1, 1)


class TestLimit:
    def test_stops_after_the_limit(self):
        r = count_allele_frequencies((v(0.1, pos=i) for i in range(50)), limit=5)
        assert r["checked"] == 5

    def test_a_limit_of_exactly_the_number_of_records(self):
        assert count_allele_frequencies([v(0.1), v(0.2)], limit=2)["checked"] == 2

    def test_does_not_consume_more_than_the_limit(self):
        seen = []

        def gen():
            for i in range(100):
                seen.append(i)
                yield v(0.1, pos=i)

        count_allele_frequencies(gen(), limit=3)
        assert len(seen) <= 4  # one lookahead at most


class TestEmpty:
    def test_no_records_is_zero_checked(self):
        r = count_allele_frequencies([], limit=10)
        assert (r["checked"], r["with_af"]) == (0, 0)


class TestExamples:
    def test_keeps_the_first_five_as_readable_lines(self):
        r = count_allele_frequencies([v(0.1, pos=i) for i in range(1, 9)], limit=8)
        assert len(r["examples"]) == 5
        assert "22:1 A>T" in r["examples"][0] and "0.1" in r["examples"][0]


class TestRunAsAScript:
    """The runbook runs it as `python path/to/validate_af_extraction.py <vcf>`."""

    def _run(self, *args):
        import os
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        script = Path(__file__).resolve().parents[2] / "validation" / "validate_af_extraction.py"
        return subprocess.run([sys.executable, str(script), *args], capture_output=True,
                              text=True, env=env, cwd="/", timeout=120)

    def test_help_starts_without_pythonpath(self):
        r = self._run("--help")
        assert r.returncode == 0, r.stderr
        assert "vcf" in r.stdout.lower()

    def test_a_missing_file_exits_nonzero_with_the_reason(self, tmp_path):
        r = self._run(str(tmp_path / "nope.vcf.gz"))
        assert r.returncode != 0
        assert "nope.vcf.gz" in (r.stderr + r.stdout)


class TestWithoutCyvcf2:
    """CI's test environment has no cyvcf2, and so can a user's shell. The script must
    still start, show help and report a missing file, and say clearly what is missing
    when it needs the library, instead of crashing on import."""

    _RUNNER = (
        "import runpy, sys\n"
        "sys.modules['cyvcf2'] = None  # `import cyvcf2` raises ImportError\n"
        "script = sys.argv[1]; sys.argv = sys.argv[1:]\n"
        "runpy.run_path(script, run_name='__main__')\n"
    )

    def _run(self, *args):
        import os
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        script = Path(__file__).resolve().parents[2] / "validation" / "validate_af_extraction.py"
        return subprocess.run([sys.executable, "-c", self._RUNNER, str(script), *args],
                              capture_output=True, text=True, env=env, cwd="/", timeout=120)

    def test_help_works_without_cyvcf2(self):
        r = self._run("--help")
        assert r.returncode == 0, r.stderr

    def test_a_missing_file_is_reported_without_cyvcf2(self, tmp_path):
        r = self._run(str(tmp_path / "nope.vcf.gz"))
        assert r.returncode == 2
        assert "nope.vcf.gz" in r.stderr

    def test_a_real_file_without_cyvcf2_says_what_is_missing(self, tmp_path):
        f = tmp_path / "x.vcf.gz"
        f.write_bytes(b"")
        r = self._run(str(f))
        assert r.returncode == 2
        assert "cyvcf2" in r.stderr
