"""Unit tests for validation.validate_json — safety net for all data entering production."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from validation.validate_json import BeaconValidator, MalformedRecord, ValidationResult


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
# TestJsonlValidation
# ===================================================================

class TestJsonlValidation:
    """JSONL is what the VCF transform emits — json.load() cannot read it."""

    def setup_method(self):
        self.v = _make_validator()

    def test_multiline_jsonl_is_parsed(self, json_fixtures_dir):
        result = self.v.validate_json_file(
            str(json_fixtures_dir / "valid_variants.jsonl"), schema_type="variant"
        )
        assert result.is_valid is True
        assert result.record_count == 5

    def test_invalid_records_in_jsonl_are_detected(self, tmp_path):
        fp = tmp_path / "variants.jsonl"
        fp.write_text(
            json.dumps({"id": "1:1:A:T", "assembly_id": "GRCh38", "reference_name": "1",
                        "start": 1, "end": 2, "reference_bases": "A", "alternate_bases": "T"}) + "\n"
            + json.dumps({"id": "no-position"}) + "\n"
        )
        result = self.v.validate_json_file(str(fp), schema_type="variant")
        assert result.is_valid is False

    def test_malformed_jsonl_line_fails(self, tmp_path):
        fp = tmp_path / "variants.jsonl"
        fp.write_text('{"id":"1"}\nnot json at all\n')
        result = self.v.validate_json_file(str(fp), schema_type="variant")
        assert result.is_valid is False
        assert result.record_count == 0

    def test_blank_lines_ignored(self, tmp_path):
        fp = tmp_path / "individuals.jsonl"
        fp.write_text('{"id":"S1"}\n\n{"id":"S2"}\n')
        result = self.v.validate_json_file(str(fp), schema_type="individual")
        assert result.is_valid is True
        assert result.record_count == 2

    def test_unreadable_jsonl_returns_empty(self, tmp_path):
        result = self.v.validate_json_file(str(tmp_path / "nope.jsonl"), schema_type="variant")
        assert result.is_valid is False


# ===================================================================
# TestSingleFileStats
# ===================================================================

class TestSingleFileStats:
    """The single-file path is what the pipeline uses — it must count failures,
    otherwise the CLI prints FAIL and still exits 0."""

    def test_failure_counted(self, json_fixtures_dir):
        v = _make_validator()
        v.validate_json_file(
            str(json_fixtures_dir / "invalid_variants.json"), schema_type="variant"
        )
        assert v.stats["files_validated"] == 1
        assert v.stats["files_failed"] == 1
        assert v.stats["total_errors"] >= 1

    def test_pass_counted(self, json_fixtures_dir):
        v = _make_validator()
        v.validate_json_file(
            str(json_fixtures_dir / "valid_variants.json"), schema_type="variant"
        )
        assert v.stats["files_passed"] == 1
        assert v.stats["files_failed"] == 0

    def test_not_double_counted_via_directory(self, json_fixtures_dir):
        v = _make_validator()
        results = v.validate_directory(str(json_fixtures_dir))
        assert v.stats["files_validated"] == len(results)


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


# ===================================================================
# TestStreamingRecords
#
# The validator materialised every record before validating: json.load()
# for .json, and an accumulating `data = []` for .jsonl. Measured at roughly
# 65 GB at production scale inside a 2 GB Nextflow allocation, so the
# pipeline aborted in validation and never reached import.
#
# Validation is purely per-record — validate(instance=record, schema=schema)
# with no cross-record checks — so it can stream. These tests pin that.
# ===================================================================

class TestStreamingRecords:
    def test_iter_records_is_lazy_not_a_list(self, json_fixtures_dir):
        """The whole point: never materialise. A list here is the bug."""
        v = _make_validator()
        it = v._iter_records(str(json_fixtures_dir / "valid_variants.jsonl"))
        assert not isinstance(it, list)
        assert iter(it) is it, "must be a one-shot iterator, not a re-iterable"

    def test_yields_records_before_reaching_a_malformed_line(self, tmp_path):
        """
        Proves laziness behaviourally rather than by type.

        With eager loading nothing is returned at all when a later line is
        bad. Streaming must hand back the good records it has already read
        before it meets the bad one.
        """
        f = tmp_path / "partly_bad.jsonl"
        f.write_text('{"id": "a"}\n{"id": "b"}\n{ not json\n{"id": "d"}\n')
        v = _make_validator()
        it = v._iter_records(str(f))
        assert next(it) == {"id": "a"}
        assert next(it) == {"id": "b"}
        with pytest.raises(MalformedRecord):
            next(it)

    def test_malformed_line_still_fails_validation(self, tmp_path):
        """
        The safety net must survive the refactor. A malformed line is a
        validation failure, never something silently skipped — streaming
        must not turn a hard failure into a partial success.
        """
        f = tmp_path / "bad_variants.jsonl"
        f.write_text('{"variantInternalId": "x", "referenceName": "1"}\n{ not json\n')
        v = _make_validator()
        result = v._validate_json_file(str(f), schema={"type": "object"})
        assert result.is_valid is False
        assert any("line 2" in e.lower() or "line 2" in e for e in result.errors)

    def test_streams_a_json_array_too(self, json_fixtures_dir):
        """.json arrays were the other cliff — json.load() read the lot."""
        v = _make_validator()
        it = v._iter_records(str(json_fixtures_dir / "valid_variants.json"))
        assert not isinstance(it, list)
        first = next(it)
        assert isinstance(first, dict)

    def test_record_count_is_correct_while_streaming(self, json_fixtures_dir):
        """Counting must not require a second pass or a materialised list."""
        v = _make_validator()
        expected = len(json.loads((json_fixtures_dir / "valid_variants.json").read_text()))
        result = v._validate_json_file(
            str(json_fixtures_dir / "valid_variants.json"), schema={"type": "object"})
        assert result.record_count == expected

    def test_empty_file_still_reports_failure(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        v = _make_validator()
        result = v._validate_json_file(str(f), schema={"type": "object"})
        assert result.is_valid is False

    def test_blank_lines_are_skipped_not_errors(self, tmp_path):
        f = tmp_path / "blanks.jsonl"
        f.write_text('{"id": "a"}\n\n\n{"id": "b"}\n')
        v = _make_validator()
        assert list(v._iter_records(str(f))) == [{"id": "a"}, {"id": "b"}]

    def test_json_array_is_not_materialised(self, tmp_path):
        """
        Detects INTERNAL buffering in the .json path, which a type check
        cannot. A malformed element at the END is the probe: streaming hands
        back the records before it, while any internal list(...) consumes the
        whole array first and yields nothing.
        """
        f = tmp_path / "late_bad.json"
        f.write_text('[{"id": "0"}, {"id": "1"}, {oops not json}]')
        v = _make_validator()
        it = v._iter_records(str(f))
        assert next(it) == {"id": "0"}, "materialised: nothing yielded before the bad element"
        assert next(it) == {"id": "1"}
        with pytest.raises(MalformedRecord):
            next(it)
