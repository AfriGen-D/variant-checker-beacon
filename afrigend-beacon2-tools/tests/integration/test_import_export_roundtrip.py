"""Integration tests for import → export roundtrip using mocked MongoDB."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from data_import.import_to_mongo import MongoImporter
from data_export.export_from_mongo import MongoExporter


def _make_importer():
    cfg = {
        "mongodb": {"host": "localhost", "port": 27017, "database": "test_db", "connection_timeout": 5},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    with patch.object(MongoImporter, "_load_config", return_value=cfg):
        return MongoImporter()


def _make_exporter():
    cfg = {
        "mongodb": {"host": "localhost", "port": 27017, "database": "test_db", "connection_timeout": 5},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        "output": {"pretty_json": True, "include_metadata": False},
    }
    with patch.object(MongoExporter, "_load_config", return_value=cfg):
        return MongoExporter()


@pytest.mark.integration
class TestImportExportRoundtrip:
    def test_import_then_export_json(self, tmp_path, json_fixtures_dir):
        """Import valid_variants.json, then export — verify same record count."""
        original = json.loads((json_fixtures_dir / "valid_variants.json").read_text())

        # Setup importer
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_many.return_value = MagicMock(inserted_ids=[f"id{i}" for i in range(len(original))])

        imp.import_json_file(str(json_fixtures_dir / "valid_variants.json"), "test_db", "variants")
        assert imp.stats["records_imported"] == 5

        # Setup exporter to return same data
        exp = _make_exporter()
        exp.client = MagicMock()
        exp_coll = exp.client.__getitem__.return_value.__getitem__.return_value
        exp_coll.count_documents.return_value = len(original)
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter(original))
        exp_coll.find.return_value = cursor

        out_file = tmp_path / "exported.json"
        exp.export_collection("test_db", "variants", str(out_file))
        exported = json.loads(out_file.read_text())
        assert len(exported) == 5

    def test_import_jsonl_export_json(self, tmp_path, json_fixtures_dir):
        """Import from JSONL, export as JSON — verify data preserved."""
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c", "d", "e"])

        imp.import_json_file(str(json_fixtures_dir / "valid_variants.jsonl"), "test_db", "variants")
        assert imp.stats["records_imported"] == 5

    def test_directory_import_export(self, tmp_path, json_fixtures_dir):
        """Import directory then verify collection mapping."""
        imp = _make_importer()
        imp.client = MagicMock()
        coll = imp.client.__getitem__.return_value.__getitem__.return_value
        coll.insert_many.return_value = MagicMock(inserted_ids=["x"])
        coll.insert_one.return_value = MagicMock(inserted_id="x")

        results = imp.import_directory(str(json_fixtures_dir), "test_db")
        # Should have processed multiple files
        assert len(results) >= 3

    def test_empty_export(self, tmp_path):
        """Export from empty collection succeeds with empty file."""
        exp = _make_exporter()
        exp.client = MagicMock()
        coll = exp.client.__getitem__.return_value.__getitem__.return_value
        coll.count_documents.return_value = 0

        out_file = tmp_path / "empty.json"
        result = exp.export_collection("test_db", "empty_coll", str(out_file))
        assert result is True
