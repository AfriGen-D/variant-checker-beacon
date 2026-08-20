"""Unit tests for data_import.import_to_mongo."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from pymongo.errors import BulkWriteError, ConnectionFailure

from data_import.import_to_mongo import MongoImporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_importer(**cfg_overrides) -> MongoImporter:
    cfg = {
        "mongodb": {"host": "localhost", "port": 27017, "database": "test_db", "connection_timeout": 5},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    cfg.update(cfg_overrides)
    with patch.object(MongoImporter, "_load_config", return_value=cfg):
        return MongoImporter()


# ===================================================================
# TestLoadJsonFile
# ===================================================================

class TestIterJsonFile:
    """
    The .json branch used json.load(), reading the whole array before a
    single record was inserted — the same cliff the .jsonl branch was already
    fixed for. These preserve the previous BEHAVIOURS while requiring that
    nothing is materialised.
    """

    def setup_method(self):
        self.imp = _make_importer()

    def test_load_array(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}, {"id": "2"}]))
        assert len(list(self.imp._iter_json_file(str(fp)))) == 2

    def test_load_single_object_wrapped(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps({"id": "1"}))
        data = list(self.imp._iter_json_file(str(fp)))
        assert len(data) == 1
        assert data[0]["id"] == "1"

    def test_invalid_json_yields_nothing(self, tmp_path):
        # Preserves the old contract: the importer logs and imports nothing
        # rather than raising. (The VALIDATOR is the component that fails
        # hard on malformed input; that is its job, not the importer's.)
        fp = tmp_path / "bad.json"
        fp.write_text("not valid json {{{")
        assert list(self.imp._iter_json_file(str(fp))) == []

    def test_non_dict_non_list_yields_nothing(self, tmp_path):
        fp = tmp_path / "num.json"
        fp.write_text("42")
        assert list(self.imp._iter_json_file(str(fp))) == []

    def test_is_a_generator_not_a_list(self, tmp_path):
        """The anti-regression for this whole issue."""
        import inspect
        assert inspect.isgeneratorfunction(MongoImporter._iter_json_file)

    def test_is_lazy(self, tmp_path):
        """Yields the first record without having read the whole array."""
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": str(i)} for i in range(500)]))
        it = self.imp._iter_json_file(str(fp))
        assert next(it) == {"id": "0"}
        assert iter(it) is it

    def test_does_not_materialise_the_array(self, tmp_path):
        """
        Detects INTERNAL buffering, which the generator-function check cannot.

        A malformed element at the END of the array is the probe: streaming
        hands back the records before it, while any internal `list(...)` — the
        exact regression this issue is about — consumes the whole array first,
        hits the parse error, and yields nothing at all.

        Written after a mutation test showed that wrapping ijson.items() in
        list() passed every other test in this class.
        """
        fp = tmp_path / "late_bad.json"
        fp.write_text('[{"id": "0"}, {"id": "1"}, {oops not json}]')
        it = self.imp._iter_json_file(str(fp))
        assert next(it) == {"id": "0"}, "materialised: nothing was yielded before the bad element"
        assert next(it) == {"id": "1"}


# ===================================================================
# TestLoadJsonlFile
# ===================================================================

class TestIterJsonlFile:
    def setup_method(self):
        self.imp = _make_importer()

    def test_load_multiple_lines(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        lines = [json.dumps({"id": str(i)}) for i in range(5)]
        fp.write_text("\n".join(lines))
        assert len(list(self.imp._iter_jsonl_file(str(fp)))) == 5

    def test_skips_blank_lines(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\n\n{"id":"2"}\n')
        assert len(list(self.imp._iter_jsonl_file(str(fp)))) == 2

    def test_skips_invalid_line(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\nbad line\n{"id":"2"}\n')
        assert len(list(self.imp._iter_jsonl_file(str(fp)))) == 2

    def test_streams_without_materializing(self, tmp_path):
        """The whole file must never be read into a list up front."""
        import inspect
        assert inspect.isgeneratorfunction(MongoImporter._iter_jsonl_file)

        fp = tmp_path / "data.jsonl"
        fp.write_text("\n".join(json.dumps({"id": str(i)}) for i in range(1000)))
        it = self.imp._iter_jsonl_file(str(fp))
        assert next(it)["id"] == "0"  # first record available before the rest


# ===================================================================
# TestConnectToMongodb
# ===================================================================

class TestConnectToMongodb:
    def test_success(self):
        imp = _make_importer()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch("data_import.import_to_mongo.MongoClient", return_value=mock_client):
            assert imp.connect_to_mongodb() is True
        assert imp.client is mock_client

    def test_connection_failure(self):
        imp = _make_importer()
        with patch("data_import.import_to_mongo.MongoClient", side_effect=ConnectionFailure("down")):
            assert imp.connect_to_mongodb() is False

    def test_custom_uri(self):
        imp = _make_importer()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch("data_import.import_to_mongo.MongoClient", return_value=mock_client) as mc:
            imp.connect_to_mongodb("mongodb://custom:9999/")
            mc.assert_called_once_with("mongodb://custom:9999/")


# ===================================================================
# TestImportJsonFile
# ===================================================================

class TestImportJsonFile:
    def test_not_connected_returns_false(self):
        imp = _make_importer()
        assert imp.import_json_file("file.json", "db", "coll") is False

    def test_file_not_found(self, tmp_path):
        imp = _make_importer()
        imp.client = MagicMock()
        assert imp.import_json_file(str(tmp_path / "missing.json"), "db", "coll") is False

    def test_successful_import(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}, {"id": "2"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is True
        assert imp.stats["records_imported"] >= 2

    def test_bulk_write_error_fails_the_import(self, tmp_path):
        """A failed batch must surface as failure, not be swallowed into a stat."""
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}, {"id": "2"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.bulk_write.side_effect = BulkWriteError({"writeErrors": [{"index": 0}]})
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is False
        assert imp.stats["errors"] >= 1

    def test_unexpected_batch_error_fails_the_import(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.bulk_write.side_effect = RuntimeError("connection reset")
        assert imp.import_json_file(str(fp), "test_db", "variants") is False
        assert imp.stats["errors"] == 1

    def test_jsonl_file_loaded(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\n{"id":"2"}\n')
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is True


# ===================================================================
# TestIdempotentImport
# ===================================================================

class TestIdempotentImport:
    """Re-running the pipeline must replace documents, not duplicate them."""

    def _import(self, tmp_path, records, filename="data.jsonl"):
        fp = tmp_path / filename
        fp.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        ok = imp.import_json_file(str(fp), "test_db", "variants")
        return imp, coll, ok

    def test_uses_bulk_write_not_insert(self, tmp_path):
        _, coll, _ = self._import(tmp_path, [{"id": "1:100:A:T"}])
        assert coll.bulk_write.called
        assert not coll.insert_many.called
        assert not coll.insert_one.called

    def test_upserts_on_natural_key(self, tmp_path):
        _, coll, _ = self._import(tmp_path, [{"id": "1:100:A:T"}, {"id": "1:200:C:G"}])
        ops = coll.bulk_write.call_args[0][0]
        assert [op._filter for op in ops] == [{"_id": "1:100:A:T"}, {"_id": "1:200:C:G"}]
        assert all(op._upsert for op in ops)

    def test_natural_key_written_to_id(self, tmp_path):
        """_id carries the natural key so a re-import replaces the document."""
        _, coll, _ = self._import(tmp_path, [{"id": "1:100:A:T", "start": 99}])
        replacement = coll.bulk_write.call_args[0][0][0]._doc
        assert replacement["_id"] == "1:100:A:T"

    def test_stale_id_is_replaced_by_natural_key(self, tmp_path):
        """An _id from a previous export must not survive into the upsert."""
        _, coll, _ = self._import(tmp_path, [{"_id": "old_object_id", "id": "1:100:A:T"}])
        op = coll.bulk_write.call_args[0][0][0]
        assert op._filter == {"_id": "1:100:A:T"}
        assert op._doc["_id"] == "1:100:A:T"

    def test_batched_not_per_document(self, tmp_path):
        """500 records at batch_size 100 → 5 round trips, not 500."""
        records = [{"id": f"1:{i}:A:T"} for i in range(500)]
        _, coll, _ = self._import(tmp_path, records)
        assert coll.bulk_write.call_count == 5

    def test_phenotype_composite_key(self, tmp_path):
        """Phenotype records have no `id` — individual + term is their key."""
        _, coll, _ = self._import(
            tmp_path, [{"individual_id": "S1", "phenotype_id": "HP:0001250"}]
        )
        assert coll.bulk_write.call_args[0][0][0]._filter == {"_id": "S1:HP:0001250"}

    def test_disease_composite_key(self, tmp_path):
        _, coll, _ = self._import(
            tmp_path, [{"individual_id": "S1", "disease_id": "MONDO:0005148"}]
        )
        assert coll.bulk_write.call_args[0][0][0]._filter == {"_id": "S1:MONDO:0005148"}

    def test_record_without_id_falls_back_to_insert(self, tmp_path):
        _, coll, ok = self._import(tmp_path, [{"start": 1}])
        op = coll.bulk_write.call_args[0][0][0]
        assert type(op).__name__ == "InsertOne"
        assert ok is True

    def test_empty_jsonl_returns_false(self, tmp_path):
        _, _, ok = self._import(tmp_path, [], filename="empty.jsonl")
        assert ok is False

    def test_empty_data_returns_false(self, tmp_path):
        fp = tmp_path / "empty.json"
        fp.write_text("[]")
        imp = _make_importer()
        imp.client = MagicMock()
        assert imp.import_json_file(str(fp), "db", "coll") is False


# ===================================================================
# TestImportDirectory
# ===================================================================

class TestImportDirectory:
    def test_not_connected(self):
        imp = _make_importer()
        assert imp.import_directory("/fake", "db") == {}

    def test_maps_filenames_to_collections(self, tmp_path):
        (tmp_path / "variants.json").write_text(json.dumps([{"id": "1"}]))
        (tmp_path / "individuals.json").write_text(json.dumps([{"id": "I1"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_one.return_value = MagicMock(inserted_id="x")
        results = imp.import_directory(str(tmp_path), "test_db")
        assert len(results) == 2

    def test_missing_dir_returns_empty(self, tmp_path):
        imp = _make_importer()
        imp.client = MagicMock()
        results = imp.import_directory(str(tmp_path / "missing"), "db")
        assert results == {}


# ===================================================================
# TestCloseConnection
# ===================================================================

class TestCloseConnection:
    def test_closes_client(self):
        imp = _make_importer()
        imp.client = MagicMock()
        imp.close_connection()
        imp.client.close.assert_called_once()

    def test_no_client_no_error(self):
        imp = _make_importer()
        imp.close_connection()  # Should not raise
