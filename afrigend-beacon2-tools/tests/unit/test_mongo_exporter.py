"""Unit tests for data_export.export_from_mongo."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pymongo.errors import ConnectionFailure

from data_export.export_from_mongo import MongoExporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exporter(**cfg_overrides) -> MongoExporter:
    cfg = {
        "mongodb": {"host": "localhost", "port": 27017, "database": "test_db", "connection_timeout": 5},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        "output": {"pretty_json": True, "include_metadata": True},
    }
    cfg.update(cfg_overrides)
    with patch.object(MongoExporter, "_load_config", return_value=cfg):
        return MongoExporter()


def _sample_docs(n=3):
    return [{"_id": ObjectId(), "id": f"DOC{i}", "value": i} for i in range(n)]


# ===================================================================
# TestConnectToMongodb
# ===================================================================

class TestConnectToMongodb:
    def test_success(self):
        exp = _make_exporter()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch("data_export.export_from_mongo.MongoClient", return_value=mock_client):
            assert exp.connect_to_mongodb() is True

    def test_failure(self):
        exp = _make_exporter()
        with patch("data_export.export_from_mongo.MongoClient", side_effect=ConnectionFailure("down")):
            assert exp.connect_to_mongodb() is False


# ===================================================================
# TestPrepareDocumentForExport
# ===================================================================

class TestPrepareDocumentForExport:
    def test_objectid_converted_to_string(self):
        exp = _make_exporter()
        oid = ObjectId()
        doc = {"_id": oid, "name": "test"}
        result = exp._prepare_document_for_export(doc)
        assert isinstance(result["_id"], str)
        assert result["_id"] == str(oid)

    def test_string_id_unchanged(self):
        exp = _make_exporter()
        doc = {"_id": "already_string", "name": "test"}
        result = exp._prepare_document_for_export(doc)
        assert result["_id"] == "already_string"

    def test_no_id_field(self):
        exp = _make_exporter()
        doc = {"name": "test"}
        result = exp._prepare_document_for_export(doc)
        assert "_id" not in result


# ===================================================================
# TestWriteJsonFile
# ===================================================================

class TestWriteJsonFile:
    def test_writes_with_metadata(self, tmp_path):
        exp = _make_exporter()
        fp = tmp_path / "out.json"
        data = [{"id": "1"}, {"id": "2"}]
        assert exp._write_json_file(data, str(fp)) is True
        content = json.loads(fp.read_text())
        assert "metadata" in content
        assert content["metadata"]["record_count"] == 2

    def test_writes_without_metadata(self, tmp_path):
        exp = _make_exporter()
        exp.config["output"]["include_metadata"] = False
        fp = tmp_path / "out.json"
        data = [{"id": "1"}]
        assert exp._write_json_file(data, str(fp)) is True
        content = json.loads(fp.read_text())
        assert isinstance(content, list)

    def test_creates_parent_dirs(self, tmp_path):
        exp = _make_exporter()
        fp = tmp_path / "sub" / "dir" / "out.json"
        assert exp._write_json_file([{"id": "1"}], str(fp)) is True
        assert fp.exists()

    def test_pretty_json(self, tmp_path):
        exp = _make_exporter()
        fp = tmp_path / "out.json"
        exp._write_json_file([{"id": "1"}], str(fp))
        text = fp.read_text()
        assert "\n" in text  # pretty-printed

    def test_compact_json(self, tmp_path):
        exp = _make_exporter()
        exp.config["output"]["pretty_json"] = False
        exp.config["output"]["include_metadata"] = False
        fp = tmp_path / "out.json"
        exp._write_json_file([{"id": "1"}], str(fp))
        text = fp.read_text()
        assert text.count("\n") <= 1  # compact


# ===================================================================
# TestExportCollection
# ===================================================================

class TestExportCollection:
    def test_not_connected(self, tmp_path):
        exp = _make_exporter()
        assert exp.export_collection("db", "coll", str(tmp_path / "out.json")) is False

    def test_empty_collection(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        coll.count_documents.return_value = 0
        result = exp.export_collection("db", "coll", str(tmp_path / "out.json"))
        assert result is True  # empty is still success

    def test_exports_documents(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        docs = _sample_docs(3)
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        coll.count_documents.return_value = 3
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter(docs))
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        coll.find.return_value = cursor

        fp = tmp_path / "out.json"
        result = exp.export_collection("db", "coll", str(fp))
        assert result is True
        assert exp.stats["records_exported"] == 3

    def test_query_filter_applied(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        coll.count_documents.return_value = 1  # must be > 0 to reach find()
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([{"_id": "x", "id": "1"}]))
        coll.find.return_value = cursor

        query = {"reference_name": "1"}
        exp.export_collection("db", "coll", str(tmp_path / "out.json"), query=query)
        coll.find.assert_called_once_with(query, None)

    def test_limit_applied(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        coll.count_documents.return_value = 1
        doc = {"_id": "x", "id": "1"}
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([doc]))
        cursor.limit.return_value = cursor
        coll.find.return_value = cursor

        exp.export_collection("db", "coll", str(tmp_path / "out.json"), limit=10)
        cursor.limit.assert_called_once_with(10)


# ===================================================================
# TestExportDatabase
# ===================================================================

class TestExportDatabase:
    def test_not_connected(self, tmp_path):
        exp = _make_exporter()
        assert exp.export_database("db", str(tmp_path)) == {}

    def test_exports_all_collections(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        db = exp.client.__getitem__.return_value
        db.list_collection_names.return_value = ["variants", "individuals"]
        # Mock each collection export
        coll = db.__getitem__.return_value
        coll.count_documents.return_value = 0
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([]))
        coll.find.return_value = cursor

        results = exp.export_database("db", str(tmp_path))
        assert "variants" in results
        assert "individuals" in results

    def test_exclude_collections(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        db = exp.client.__getitem__.return_value
        db.list_collection_names.return_value = ["variants", "system.indexes"]
        coll = db.__getitem__.return_value
        coll.count_documents.return_value = 0
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([]))
        coll.find.return_value = cursor

        results = exp.export_database("db", str(tmp_path), exclude_collections=["system.indexes"])
        assert "system.indexes" not in results


# ===================================================================
# TestExportWithAggregation
# ===================================================================

class TestExportWithAggregation:
    def test_not_connected(self, tmp_path):
        exp = _make_exporter()
        assert exp.export_with_aggregation("db", "coll", [], str(tmp_path / "out.json")) is False

    def test_aggregation_pipeline(self, tmp_path):
        exp = _make_exporter()
        exp.client = MagicMock()
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        agg_result = [{"_id": "grp1", "count": 10}]
        coll.aggregate.return_value = iter(agg_result)

        pipeline = [{"$group": {"_id": "$reference_name", "count": {"$sum": 1}}}]
        fp = tmp_path / "agg.json"
        result = exp.export_with_aggregation("db", "coll", pipeline, str(fp))
        assert result is True
        assert exp.stats["records_exported"] >= 1


# ===================================================================
# TestCloseConnection
# ===================================================================

class TestCloseConnection:
    def test_closes_client(self):
        exp = _make_exporter()
        exp.client = MagicMock()
        exp.close_connection()
        exp.client.close.assert_called_once()

    def test_no_client_safe(self):
        exp = _make_exporter()
        exp.close_connection()
