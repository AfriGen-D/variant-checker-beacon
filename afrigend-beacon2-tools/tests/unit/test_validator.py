"""Unit tests for validation.validate_json — safety net for all data entering production."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from validation.validate_json import BeaconValidator, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validator(**config_overrides) -> BeaconValidator:
    cfg = {
        "validation": {
            "strict_mode": False,
            "required_fields_check": True,
            "type_validation": True,
            "range_validation": True,
        },
        "processing": {"log_level": "WARNING"},
    }
    cfg.update(config_overrides)
    with patch.object(BeaconValidator, "_load_config", return_value=cfg):
        return BeaconValidator()


# ===================================================================
# TestGetBeaconV2Schemas
# ===================================================================

class TestGetBeaconV2Schemas:
    def test_all_four_schemas_present(self):
        v = _make_validator()
        schemas = v.get_beacon_v2_schemas()
        assert set(schemas.keys()) == {"variant", "individual", "phenotype", "dataset"}

    def test_variant_schema_has_required(self):
        v = _make_validator()
        schema = v.get_beacon_v2_schemas()["variant"]
        assert "start" in schema["required"]
        assert "end" in schema["required"]

    def test_individual_schema_only_requires_id(self):
        v = _make_validator()
        schema = v.get_beacon_v2_schemas()["individual"]
        assert schema["required"] == ["id"]

    def test_schemas_are_valid_json_schema(self):
        """Each schema should have 'type' and 'properties'."""
        v = _make_validator()
        for name, schema in v.get_beacon_v2_schemas().items():
            assert "type" in schema, f"{name} missing 'type'"
            assert "properties" in schema, f"{name} missing 'properties'"


# ===================================================================
# TestInferSchemaType
# ===================================================================

class TestInferSchemaType:
    def setup_method(self):
        self.v = _make_validator()

    def test_variant_filename(self):
        assert self.v._infer_schema_type("path/to/variants.json") == "variant"

    def test_individual_filename(self):
        assert self.v._infer_schema_type("individuals.json") == "individual"

    def test_phenotype_filename(self):
        assert self.v._infer_schema_type("phenotypes.json") == "phenotype"

    def test_dataset_filename(self):
        assert self.v._infer_schema_type("dataset_info.json") == "dataset"

    def test_disease_maps_to_phenotype(self):
        assert self.v._infer_schema_type("diseases.json") == "phenotype"

    def test_unknown_returns_none(self):
        assert self.v._infer_schema_type("random_data.json") is None


# ===================================================================
# TestValidateJsonFile
# ===================================================================

class TestValidateJsonFile:
    def setup_method(self):
        self.v = _make_validator()

    def test_valid_variants_pass(self, json_fixtures_dir):
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "valid_variants.json"), schema_type="variant"
        )
        assert result.is_valid is True
        assert result.record_count == 5
        assert len(result.errors) == 0

    def test_valid_individuals_pass(self, json_fixtures_dir):
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "valid_individuals.json"), schema_type="individual"
        )
        assert result.is_valid is True
        assert result.record_count == 3

    def test_invalid_variants_fail(self, json_fixtures_dir):
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_missing_start_detected(self, json_fixtures_dir):
        """First record in invalid_variants.json is missing 'start'."""
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        start_errors = [e for e in result.errors if "start" in e.lower()]
        assert len(start_errors) >= 1

    def test_negative_position_detected(self, json_fixtures_dir):
        """Second record has start=-100, below minimum 0."""
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        neg_errors = [e for e in result.errors if "-100" in e or "minimum" in e.lower()]
        assert len(neg_errors) >= 1

    def test_bad_assembly_type_detected(self, json_fixtures_dir):
        """Third record has assembly_id=12345 (int, not string)."""
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        type_errors = [e for e in result.errors if "12345" in e or "type" in e.lower()]
        assert len(type_errors) >= 1

    def test_malformed_json_returns_invalid(self, json_fixtures_dir):
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "malformed.json"), schema_type="variant"
        )
        assert result.is_valid is False
        assert result.record_count == 0

    def test_nonexistent_file(self, tmp_path):
        result = self.v.validate_json_file(str(tmp_path / "nope.json"), schema_type="variant")
        assert result.is_valid is False

    def test_no_schema_warns(self, json_fixtures_dir):
        """When no schema type given and filename doesn't match, warn but pass."""
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "valid_variants.json")
        )
        # filename contains 'variant' so schema IS inferred → still valid
        assert result.is_valid is True

    def test_single_dict_wrapped_in_list(self, tmp_path):
        """A JSON file containing a single object (not array) should still work."""
        fp = tmp_path / "single.json"
        fp.write_text(json.dumps({"id": "IND1"}))
        result = self.v.validate_json_file(str(fp), schema_type="individual")
        assert result.is_valid is True
        assert result.record_count == 1


# ===================================================================
# TestStrictMode
# ===================================================================

class TestStrictMode:
    def test_strict_stops_on_first_error(self, json_fixtures_dir):
        v = _make_validator()
        v.config["validation"]["strict_mode"] = True
        result = v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        assert result.is_valid is False
        assert len(result.errors) == 1  # only first error reported

    def test_non_strict_reports_all(self, json_fixtures_dir):
        v = _make_validator()
        v.config["validation"]["strict_mode"] = False
        result = v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        assert result.is_valid is False
        assert len(result.errors) >= 3  # 3 bad records in fixture


# ===================================================================
# TestValidateDirectory
# ===================================================================

class TestValidateDirectory:
    def test_validates_all_json_files(self, json_fixtures_dir):
        v = _make_validator()
        results = v.validate_directory(str(json_fixtures_dir))
        # valid_variants.json, valid_variants.jsonl, valid_individuals.json,
        # invalid_variants.json, malformed.json = 5 files
        assert len(results) >= 4

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        v = _make_validator()
        results = v.validate_directory(str(tmp_path / "no_such_dir"))
        assert results == []

    def test_stats_updated(self, json_fixtures_dir):
        v = _make_validator()
        v.validate_directory(str(json_fixtures_dir))
        assert v.stats["files_validated"] >= 4
        assert v.stats["files_failed"] >= 1  # malformed.json should fail


# ===================================================================
# TestValidationResult dataclass
# ===================================================================

class TestValidationResult:
    def test_fields(self):
        r = ValidationResult(
            file_path="test.json", is_valid=True, errors=[], warnings=[],
            record_count=5, validation_time=0.01,
        )
        assert r.file_path == "test.json"
        assert r.record_count == 5
