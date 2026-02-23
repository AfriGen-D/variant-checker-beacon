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

class TestLoadJsonFile:
    def setup_method(self):
        self.imp = _make_importer()

    def test_load_array(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}, {"id": "2"}]))
        data = self.imp._load_json_file(str(fp))
        assert len(data) == 2

    def test_load_single_object_wrapped(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps({"id": "1"}))
        data = self.imp._load_json_file(str(fp))
        assert len(data) == 1
        assert data[0]["id"] == "1"

    def test_invalid_json_returns_empty(self, tmp_path):
        fp = tmp_path / "bad.json"
        fp.write_text("not valid json {{{")
        data = self.imp._load_json_file(str(fp))
        assert data == []

    def test_non_dict_non_list_returns_empty(self, tmp_path):
        fp = tmp_path / "num.json"
        fp.write_text("42")
        data = self.imp._load_json_file(str(fp))
        assert data == []


# ===================================================================
# TestLoadJsonlFile
# ===================================================================

class TestLoadJsonlFile:
    def setup_method(self):
        self.imp = _make_importer()

    def test_load_multiple_lines(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        lines = [json.dumps({"id": str(i)}) for i in range(5)]
        fp.write_text("\n".join(lines))
        data = self.imp._load_jsonl_file(str(fp))
        assert len(data) == 5

    def test_skips_blank_lines(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\n\n{"id":"2"}\n')
        data = self.imp._load_jsonl_file(str(fp))
        assert len(data) == 2

    def test_skips_invalid_line(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\nbad line\n{"id":"2"}\n')
        data = self.imp._load_jsonl_file(str(fp))
        assert len(data) == 2


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
        coll.insert_many.return_value = MagicMock(inserted_ids=["a", "b"])
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is True
        assert imp.stats["records_imported"] >= 2

    def test_bulk_write_error_handled(self, tmp_path):
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"id": "1"}, {"id": "2"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_many.side_effect = BulkWriteError({"writeErrors": [{"index": 0}]})
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is True
        assert imp.stats["errors"] >= 1

    def test_id_field_stripped(self, tmp_path):
        """_id fields should be removed to avoid MongoDB conflicts."""
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps([{"_id": "old_id", "id": "1"}]))
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_one.return_value = MagicMock(inserted_id="new_id")
        imp.import_json_file(str(fp), "test_db", "variants")
        call_args = coll.insert_one.call_args[0][0]
        assert "_id" not in call_args

    def test_jsonl_file_loaded(self, tmp_path):
        fp = tmp_path / "data.jsonl"
        fp.write_text('{"id":"1"}\n{"id":"2"}\n')
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_many.return_value = MagicMock(inserted_ids=["a", "b"])
        result = imp.import_json_file(str(fp), "test_db", "variants")
        assert result is True

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
