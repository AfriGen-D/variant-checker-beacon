"""scripts/submit_multi_vcf.sh: submit many VCFs as Slurm jobs, with a stand-in sbatch.

The stand-in records every sbatch call (arguments and script) and answers --parsable
with increasing job ids, so the tests check what would be submitted, in what order, and
with which dependency, without a cluster.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SUBMIT = REPO / "scripts" / "submit_multi_vcf.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

SBATCH_SHIM = """#!/bin/sh
# Stand-in sbatch: log the call, number the jobs, print the id for --parsable.
LOG="$SBATCH_SHIM_DIR/calls.log"; N="$SBATCH_SHIM_DIR/counter"
[ -f "$N" ] || echo 1000 > "$N"
ID=$(( $(cat "$N") + 1 )); echo $ID > "$N"
echo "JOB $ID :: $*" >> "$LOG"
for a in "$@"; do last="$a"; done
echo "SCRIPT $ID :: $last" >> "$LOG"
echo $ID
"""


@pytest.fixture
def env(tmp_path):
    shim = tmp_path / "shim"
    shim.mkdir()
    f = shim / "sbatch"
    f.write_text(SBATCH_SHIM)
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    e = {k: v for k, v in os.environ.items() if k not in ("DATASET_ID", "DATASET_FILE")}
    e["PATH"] = f"{shim}{os.pathsep}/usr/bin:/bin"
    e["SBATCH_SHIM_DIR"] = str(shim)
    return e, shim


def _vcfs(tmp_path, names=("chr1.vcf.gz", "chr2.vcf.gz", "chr3.vcf.gz")):
    d = tmp_path / "vcfs"
    d.mkdir(exist_ok=True)
    out = []
    for n in names:
        (d / n).write_text("")
        out.append(str(d / n))
    return out


def _dataset(tmp_path):
    f = tmp_path / "dataset.yaml"
    f.write_text("dataset:\n  id: MY_DATA\n  name: My data\n")
    return str(f)


def _run(env, tmp_path, *args):
    e, _ = env
    return subprocess.run(["bash", str(SUBMIT), *args], capture_output=True, text=True, env=e,
                          cwd=str(tmp_path), timeout=120)


def _base(tmp_path, *vcfs, extra=()):
    return ["--dataset-file", _dataset(tmp_path), "--container", "/x/tools.sif",
            "--output", str(tmp_path / "out"), *extra, *vcfs]


def _calls(env):
    log = env[1] / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


class TestTransformArray:
    def test_submits_one_array_job_with_one_task_per_file(self, env, tmp_path):
        vcfs = _vcfs(tmp_path)
        r = _run(env, tmp_path, *_base(tmp_path, *vcfs))
        assert r.returncode == 0, r.stdout + r.stderr
        jobs = [c for c in _calls(env) if c.startswith("JOB")]
        assert len(jobs) == 1, jobs                      # transform only: no import without --import
        script = (tmp_path / "out" / "transform.sbatch").read_text()
        assert "#SBATCH --array=1-3%3" in script   # default 4 at once, clamped to the 3 files

    def test_the_default_is_four_at_once(self, env, tmp_path):
        names = tuple(f"c{i}.vcf.gz" for i in range(1, 7))
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path, names)))
        assert "#SBATCH --array=1-6%4" in (tmp_path / "out" / "transform.sbatch").read_text()

    def test_max_parallel_caps_the_array(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--max-parallel", "2")))
        assert "#SBATCH --array=1-3%2" in (tmp_path / "out" / "transform.sbatch").read_text()

    def test_max_parallel_larger_than_the_files_is_clamped(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path, ("a.vcf.gz",)), extra=("--max-parallel", "9")))
        assert "#SBATCH --array=1-1%1" in (tmp_path / "out" / "transform.sbatch").read_text()

    def test_the_file_list_is_in_order_with_absolute_paths(self, env, tmp_path):
        vcfs = _vcfs(tmp_path)
        _run(env, tmp_path, *_base(tmp_path, *vcfs))
        assert (tmp_path / "out" / "vcf_list.txt").read_text().split() == vcfs

    def test_each_task_transforms_without_importing(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path)))
        s = (tmp_path / "out" / "transform.sbatch").read_text()
        assert "--skip-import" in s and "--import-only" not in s
        assert "SLURM_ARRAY_TASK_ID" in s
        assert "--dataset-file" in s and "--container /x/tools.sif" in s

    def test_resources_are_requested(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path),
                                   extra=("--cpus", "8", "--mem", "64G", "--time", "2-00:00:00")))
        s = (tmp_path / "out" / "transform.sbatch").read_text()
        assert "#SBATCH --cpus-per-task=8" in s
        assert "#SBATCH --mem=64G" in s
        assert "#SBATCH --time=2-00:00:00" in s

    def test_the_job_scripts_are_valid_bash(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--import",)))
        for name in ("transform.sbatch", "import.sbatch"):
            r = subprocess.run(["bash", "-n", str(tmp_path / "out" / name)], capture_output=True, text=True)
            assert r.returncode == 0, r.stderr

    def test_extra_sbatch_options_reach_every_submission(self, env, tmp_path):
        _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path),
                                   extra=("--import", "--sbatch-args", "--nodelist=compute-[205,209]")))
        jobs = [c for c in _calls(env) if c.startswith("JOB")]
        assert len(jobs) == 2 and all("--nodelist=compute-[205,209]" in j for j in jobs), jobs


class TestImportJob:
    def test_import_waits_for_every_transform_task(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--import",)))
        assert r.returncode == 0, r.stdout + r.stderr
        jobs = [c for c in _calls(env) if c.startswith("JOB")]
        assert len(jobs) == 2
        array_id = jobs[0].split()[1]
        assert f"--dependency=afterok:{array_id}" in jobs[1]
        assert "--kill-on-invalid-dep=yes" in jobs[1]    # a failed task cancels the import, it does not hang

    def test_import_job_imports_every_listed_file_without_transforming(self, env, tmp_path):
        vcfs = _vcfs(tmp_path)
        _run(env, tmp_path, *_base(tmp_path, *vcfs, extra=("--import",)))
        s = (tmp_path / "out" / "import.sbatch").read_text()
        assert "--import-only" in s
        assert "--skip-import" not in s
        # It walks the same list the transform array used, in the same order, so the
        # file list is the single source of truth for both stages.
        assert 'done < "' + str(tmp_path / "out" / "vcf_list.txt") + '"' in s
        assert (tmp_path / "out" / "vcf_list.txt").read_text().split() == vcfs

    def test_import_only_submits_just_the_import_with_no_dependency(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--import-only",)))
        assert r.returncode == 0, r.stdout + r.stderr
        jobs = [c for c in _calls(env) if c.startswith("JOB")]
        assert len(jobs) == 1 and "import.sbatch" in jobs[0] and "--dependency" not in jobs[0], jobs

    def test_import_and_import_only_contradict(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--import", "--import-only")))
        assert r.returncode != 0 and "contradict" in r.stderr
        assert _calls(env) == []

    def test_without_import_nothing_touches_a_database_and_the_user_is_told_how(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path)))
        assert not (tmp_path / "out" / "import.sbatch").exists()
        assert "--import" in r.stdout


class TestDryRun:
    def test_writes_the_scripts_and_submits_nothing(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--import", "--dry-run")))
        assert r.returncode == 0, r.stdout + r.stderr
        assert _calls(env) == []
        assert (tmp_path / "out" / "transform.sbatch").exists()
        assert (tmp_path / "out" / "import.sbatch").exists()


class TestRefusals:
    def test_no_files(self, env, tmp_path):
        r = _run(env, tmp_path, "--dataset-file", _dataset(tmp_path), "--container", "/x/t.sif")
        assert r.returncode != 0 and "VCF" in r.stderr
        assert _calls(env) == []

    def test_a_missing_file(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, str(tmp_path / "nope.vcf.gz")))
        assert r.returncode != 0 and "nope.vcf.gz" in r.stderr
        assert _calls(env) == []

    def test_no_dataset(self, env, tmp_path):
        r = _run(env, tmp_path, "--container", "/x/t.sif", *_vcfs(tmp_path))
        assert r.returncode != 0 and "dataset" in r.stderr.lower()
        assert _calls(env) == []

    def test_no_container(self, env, tmp_path):
        r = _run(env, tmp_path, "--dataset-file", _dataset(tmp_path), *_vcfs(tmp_path))
        assert r.returncode != 0 and "container" in r.stderr.lower()

    def test_two_files_with_the_same_name_would_overwrite_each_other(self, env, tmp_path):
        a = tmp_path / "a"; b = tmp_path / "b"; a.mkdir(); b.mkdir()
        (a / "x.vcf.gz").write_text(""); (b / "x.vcf.gz").write_text("")
        r = _run(env, tmp_path, *_base(tmp_path, str(a / "x.vcf.gz"), str(b / "x.vcf.gz")))
        assert r.returncode != 0 and "x.vcf.gz" in r.stderr
        assert _calls(env) == []

    def test_a_path_with_a_space_is_refused(self, env, tmp_path):
        d = tmp_path / "my vcfs"; d.mkdir(); (d / "a.vcf.gz").write_text("")
        r = _run(env, tmp_path, *_base(tmp_path, str(d / "a.vcf.gz")))
        assert r.returncode != 0 and "space" in r.stderr.lower()

    def test_a_non_numeric_parallelism(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--max-parallel", "lots")))
        assert r.returncode != 0 and "max-parallel" in r.stderr

    def test_an_unknown_option(self, env, tmp_path):
        r = _run(env, tmp_path, *_base(tmp_path, *_vcfs(tmp_path), extra=("--bogus",)))
        assert r.returncode != 0 and "--bogus" in r.stderr
