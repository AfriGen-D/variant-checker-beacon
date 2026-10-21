"""Run scripts/run_ilifu_pipeline.sh as a user would, with stand-in container runtimes.

The script is `set -euo pipefail`, so an unset variable used without a default is a hard
failure. That is shell-version dependent: macOS's old bash tolerated one such expansion in
the Docker branch, Linux's bash 4/5 does not, so the Docker route was broken on every Linux
host and nobody noticed from a Mac. These tests run the real script under whatever bash the
machine has (CI runs Linux), with CONTAINER_BIND deliberately unset.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "run_ilifu_pipeline.sh"
VCF = REPO / "afrigend-beacon2-tools" / "tests" / "fixtures" / "vcf" / "sample_multi.vcf"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _shim(tmp_path, name):
    """A stand-in runtime that accepts any arguments and succeeds."""
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    f = d / name
    f.write_text("#!/bin/sh\nexit 0\n")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return d


def _run(tmp_path, *args, runtime=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CONTAINER_BIND", "DATASET_ID", "DATASET_FILE", "BEACON_CONTAINER", "BEACON_RUNTIME")}
    path = os.pathsep.join([str(_shim(tmp_path, runtime))] if runtime else []) + os.pathsep + "/usr/bin:/bin"
    env["PATH"] = path
    return subprocess.run(["bash", str(SCRIPT), str(VCF), *args, "--output", str(tmp_path / "out")],
                          capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)


class TestDockerRoute:
    def test_dry_run_works_with_container_bind_unset(self, tmp_path):
        r = _run(tmp_path, "--dataset-id", "X", "--container", "some/image:tag",
                 "--runtime", "docker", "--dry-run", runtime="docker")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "unbound variable" not in r.stderr
        assert "DRY RUN" in r.stdout

    def test_container_bind_is_honoured_when_set(self, tmp_path):
        r = _run(tmp_path, "--dataset-id", "X", "--container", "some/image:tag",
                 "--runtime", "docker", "--dry-run", runtime="docker")
        assert r.returncode == 0  # control for the next: same call, now with the variable set
        env_bind = tmp_path / "data"
        env_bind.mkdir()
        os_env = {**os.environ, "CONTAINER_BIND": f"{env_bind}"}
        r2 = subprocess.run(
            ["bash", str(SCRIPT), str(VCF), "--dataset-id", "X", "--container", "some/image:tag",
             "--runtime", "docker", "--dry-run", "--output", str(tmp_path / "out2")],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120,
            env={**os_env, "PATH": f"{_shim(tmp_path, 'docker')}{os.pathsep}/usr/bin:/bin"})
        assert r2.returncode == 0, r2.stdout + r2.stderr
        assert "unbound variable" not in r2.stderr


class TestSingularityRoute:
    def test_dry_run_works_with_container_bind_unset(self, tmp_path):
        sif = tmp_path / "tools.sif"
        sif.write_text("")
        r = _run(tmp_path, "--dataset-id", "X", "--container", str(sif),
                 "--runtime", "singularity", "--dry-run", runtime="singularity")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "unbound variable" not in r.stderr


class TestRefusals:
    def test_no_dataset_is_refused(self, tmp_path):
        r = _run(tmp_path, "--container", "some/image:tag", "--runtime", "docker", "--dry-run", runtime="docker")
        assert r.returncode == 1
        assert "dataset" in r.stderr.lower()


class TestImportOnly:
    """--import-only reuses an earlier --skip-import run's output folder."""

    def _out(self, tmp_path, make_variants=True):
        out = tmp_path / "out"
        (out / "vcf_output").mkdir(parents=True)
        if make_variants:
            (out / "vcf_output" / "variants_batch.jsonl").write_text('{"id": "1"}\n')
        return out

    def _call(self, tmp_path, *extra):
        env = {k: v for k, v in os.environ.items() if k not in ("CONTAINER_BIND", "DATASET_ID", "DATASET_FILE")}
        env["PATH"] = f"{_shim(tmp_path, 'docker')}{os.pathsep}/usr/bin:/bin"
        return subprocess.run(
            ["bash", str(SCRIPT), str(VCF), "--dataset-id", "X", "--container", "some/image:tag",
             "--runtime", "docker", "--output", str(tmp_path / "out"), *extra],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)

    def test_dry_run_with_existing_output_is_accepted(self, tmp_path):
        self._out(tmp_path)
        r = self._call(tmp_path, "--import-only", "--dry-run")
        assert r.returncode == 0, r.stdout + r.stderr

    def test_missing_output_is_refused_with_the_reason(self, tmp_path):
        self._out(tmp_path, make_variants=False)
        r = self._call(tmp_path, "--import-only", "--skip-validate")
        assert r.returncode == 1
        assert "variants_batch.jsonl" in (r.stdout + r.stderr)
        assert "--import-only" in (r.stdout + r.stderr)

    def test_contradicting_flags_are_refused(self, tmp_path):
        self._out(tmp_path)
        r = self._call(tmp_path, "--import-only", "--skip-import")
        assert r.returncode == 1
        assert "contradict" in r.stderr

    def test_it_does_not_transform_or_validate(self, tmp_path):
        # The stand-in docker records every call. With --import-only and no database
        # to reach, the run must stop at the import step without ever having started
        # the transform or the validator.
        self._out(tmp_path)
        pheno = tmp_path / "pheno.csv"
        pheno.write_text("id,sex\nA,F\n")      # given on purpose: --import-only must still not transform it
        log = tmp_path / "docker_calls.log"
        shim = _shim(tmp_path, "docker")
        (shim / "docker").write_text(f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')
        (shim / "nc").write_text("#!/bin/sh\nexit 0\n")      # pretend the SSH tunnel is already up
        (shim / "nc").chmod(0o755)
        env = {k: v for k, v in os.environ.items() if k not in ("CONTAINER_BIND",)}
        env["PATH"] = f"{shim}{os.pathsep}/usr/bin:/bin"
        r = subprocess.run(
            ["bash", str(SCRIPT), str(VCF), "--dataset-id", "X", "--container", "some/image:tag",
             "--runtime", "docker", "--output", str(tmp_path / "out"), "--import-only",
             "--phenotypes", str(pheno)],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)
        calls = log.read_text() if log.exists() else ""
        # (Step 1 runs `vcf_to_beacon.py --help` as a startup check; a real transform has --assembly.)
        transforms = [c for c in calls.splitlines() if "vcf_to_beacon.py" in c and "--assembly" in c]
        assert not transforms, transforms
        assert "validate_json.py" not in calls, calls
        assert "phenotype_to_beacon.py" not in calls, calls
        assert "import_to_mongo.py" in calls, r.stdout + r.stderr


class TestTransformerWarnings:
    """The transformer's carrier warnings are repeated where the user will see them.

    A dataset cut from some of the samples of a larger VCF loads without an error and
    then answers yes at sites nobody carries. The transformer warns, but its line is
    buried in a long run, so the pipeline repeats the warnings from the summary.
    """

    def _prepare(self, tmp_path, warnings):
        import json
        out = tmp_path / "out" / "vcf_output"
        out.mkdir(parents=True)
        (out / "variants_batch.jsonl").write_text('{"id": "1"}\n')
        (out / "transformation_summary.json").write_text(
            json.dumps({"statistics": {"individuals_found": 4}, "warnings": warnings}))

    def _run(self, tmp_path):
        shim = tmp_path / "bin"
        shim.mkdir(exist_ok=True)
        # A stand-in runtime. `<runtime> exec --bind X IMAGE python -c CODE ARG` runs
        # the code on the host; every other call (the --help start-up check, ...) is a no-op.
        runtime = shim / "singularity"
        runtime.write_text(
            '#!/bin/sh\n'
            'while [ "$#" -gt 0 ]; do\n'
            '  if [ "$1" = python ]; then shift; if [ "$1" = -c ]; then exec python3 "$@"; fi; exit 0; fi\n'
            '  shift\n'
            'done\nexit 0\n')
        runtime.chmod(0o755)
        (shim / "nc").write_text("#!/bin/sh\nexit 0\n")
        (shim / "nc").chmod(0o755)
        (tmp_path / "image.sif").write_text("not a real image")
        py = shutil.which("python3") or "/usr/bin/python3"
        env = {k: v for k, v in os.environ.items() if k not in ("CONTAINER_BIND",)}
        env["PATH"] = os.pathsep.join([str(shim), str(Path(py).parent), "/usr/bin:/bin"])
        return subprocess.run(
            ["bash", str(SCRIPT), str(VCF), "--dataset-id", "X", "--container", str(tmp_path / "image.sif"),
             "--runtime", "singularity", "--output", str(tmp_path / "out"), "--import-only"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)

    def test_warnings_in_the_summary_are_repeated_with_what_to_do(self, tmp_path):
        self._prepare(tmp_path, ["W-ONE has no carrier", "W-TWO INFO is stale"])
        r = self._run(tmp_path)
        text = r.stdout + r.stderr
        assert "Using the existing transform output" in text, text
        assert "W-ONE has no carrier" in text and "W-TWO INFO is stale" in text
        assert "reported problems" in text
        assert "Cutting a dataset from some of the samples" in text

    def test_a_clean_summary_prints_nothing_extra(self, tmp_path):
        self._prepare(tmp_path, [])
        r = self._run(tmp_path)
        text = r.stdout + r.stderr
        assert "Using the existing transform output" in text, text   # it got past the step
        assert "reported problems" not in text

    def test_a_summary_from_an_older_transformer_has_no_warnings_key(self, tmp_path):
        import json
        self._prepare(tmp_path, [])
        path = tmp_path / "out" / "vcf_output" / "transformation_summary.json"
        path.write_text(json.dumps({"statistics": {"individuals_found": 4}}))
        r = self._run(tmp_path)
        text = r.stdout + r.stderr
        assert "Using the existing transform output" in text, text
        assert "reported problems" not in text
        assert "Traceback" not in text
