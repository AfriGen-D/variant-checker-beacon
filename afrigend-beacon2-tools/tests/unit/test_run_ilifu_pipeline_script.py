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
