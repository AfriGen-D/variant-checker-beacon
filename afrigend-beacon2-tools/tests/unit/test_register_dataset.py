"""Tests for registering a dataset record in the datasets collection."""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data_import.register_dataset import build_dataset_update, register_dataset  # noqa: E402

META = {
    "id": "MY_DATA", "name": "My data", "description": "About it",
    "assembly": "GRCh38", "contact": {"name": "A"},
}
NOW = datetime(2026, 10, 16, 1, 0, 0)


class TestBuildDatasetUpdate:
    def test_fields_match_what_the_api_reads(self):
        filt, update = build_dataset_update(META, variants=4231, samples=9, now=NOW)
        assert filt == {"_id": "MY_DATA"}
        s = update["$set"]
        assert s["name"] == "My data"
        assert s["description"] == "About it"
        assert s["assembly_id"] == "GRCh38"
        assert s["dataset_type"] == "genomics"
        assert s["contact_info"] == {"name": "A"}
        assert s["update_date"] == NOW
        assert update["$setOnInsert"] == {"create_date": NOW}

    def test_counts_are_integers(self):
        # The API only shows variantCount/sampleCount when they are ints; a float
        # such as 4231.0 (what the Mongo shell stores) is silently dropped.
        _, update = build_dataset_update(META, variants=4231, samples=9, now=NOW)
        size = update["$set"]["dataset_size"]
        assert size == {"variants": 4231, "samples": 9}
        assert all(type(v) is int for v in size.values())

    def test_unknown_samples_are_left_out_not_zero(self):
        # Zero would read as "no samples"; absence reads as "not known".
        _, update = build_dataset_update(META, variants=10, samples=None, now=NOW)
        assert update["$set"]["dataset_size"] == {"variants": 10}

    def test_unknown_counts_leave_the_size_untouched(self):
        _, update = build_dataset_update(META, variants=None, samples=None, now=NOW)
        assert "dataset_size" not in update["$set"]

    def test_assembly_argument_fills_a_missing_file_value(self):
        meta = dict(META, assembly=None)
        _, update = build_dataset_update(meta, variants=1, samples=1, now=NOW, default_assembly="GRCh37")
        assert update["$set"]["assembly_id"] == "GRCh37"

    def test_no_assembly_anywhere_is_refused(self):
        meta = dict(META, assembly=None)
        try:
            build_dataset_update(meta, variants=1, samples=1, now=NOW)
        except ValueError as e:
            assert "assembly" in str(e)
        else:
            raise AssertionError("expected ValueError")

    def test_a_missing_description_is_not_written_as_a_string(self):
        meta = dict(META, description=None)
        _, update = build_dataset_update(meta, variants=1, samples=1, now=NOW)
        assert "description" not in update["$set"]


class TestRegisterDataset:
    def _db(self, variants_in_db=4231):
        coll = MagicMock()
        variants = MagicMock()
        variants.count_documents.return_value = variants_in_db
        db = MagicMock()
        db.__getitem__.side_effect = lambda name: {"datasets": coll, "variants": variants}[name]
        return db, coll, variants

    def test_upserts_into_the_datasets_collection(self):
        db, coll, _ = self._db()
        register_dataset(db, META, samples=9, now=NOW)
        args, kwargs = coll.update_one.call_args
        assert args[0] == {"_id": "MY_DATA"}
        assert kwargs == {"upsert": True}

    def test_variant_count_comes_from_the_variants_collection(self):
        db, coll, variants = self._db(variants_in_db=4231)
        register_dataset(db, META, samples=9, now=NOW)
        variants.count_documents.assert_called_once_with({"dataset_ids": "MY_DATA"})
        assert coll.update_one.call_args[0][1]["$set"]["dataset_size"]["variants"] == 4231

    def test_zero_variants_is_refused_because_the_id_would_match_nothing(self):
        # Registering a dataset nothing belongs to is the exact silent failure this prevents.
        db, coll, _ = self._db(variants_in_db=0)
        try:
            register_dataset(db, META, samples=9, now=NOW)
        except ValueError as e:
            assert "MY_DATA" in str(e)
        else:
            raise AssertionError("expected ValueError")
        coll.update_one.assert_not_called()

    def test_second_call_updates_the_same_record(self):
        db, coll, _ = self._db()
        register_dataset(db, META, samples=9, now=NOW)
        register_dataset(db, META, samples=9, now=NOW)
        assert [c[0][0] for c in coll.update_one.call_args_list] == [{"_id": "MY_DATA"}] * 2


class TestRunAsAScript:
    """The pipeline runs these as `python path/to/script.py`, with no PYTHONPATH."""

    def _run(self, *args):
        import os
        import subprocess
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        script = Path(__file__).resolve().parents[2] / "data_import" / "register_dataset.py"
        return subprocess.run([sys.executable, str(script), *args], capture_output=True,
                              text=True, env=env, cwd="/", timeout=60)

    def test_starts_and_shows_help(self):
        r = self._run("--help")
        assert r.returncode == 0, r.stderr
        assert "dataset_file" in r.stdout

    def test_a_bad_dataset_file_exits_2_with_the_reason(self, tmp_path):
        f = tmp_path / "d.yaml"
        f.write_text("dataset:\n  id: has space\n  name: x\n")
        r = self._run(str(f), "--db", "beacon_db")
        assert r.returncode == 2
        assert "dataset.id" in r.stderr
