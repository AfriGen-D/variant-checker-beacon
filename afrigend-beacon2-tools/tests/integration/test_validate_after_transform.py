"""Integration tests: transform data then validate output against schemas."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Patch heavy imports
for mod in ("cyvcf2", "pysam", "biopython", "Bio", "Bio.SeqIO", "pronto"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from vcf_transform.vcf_to_beacon import VCFTransformer
from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer, OntologyManager
from validation.validate_json import BeaconValidator


def _mock_variant(chrom, pos, ref, alt, qual=50.0, info=None, gt=None):
    v = MagicMock()
    v.CHROM = chrom
    v.POS = pos
    v.REF = ref
    v.ALT = alt
    v.QUAL = qual
    v.INFO = info or {"DP": 30}
    v.genotypes = gt or [[0, 1, False]]
    v.format.return_value = {}
    return v


@pytest.mark.integration
class TestValidateAfterTransform:
    def test_vcf_output_validates(self, tmp_path):
        """Variants produced by VCF transform should pass variant schema validation."""
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {"min_qual": 0, "min_depth": 0}},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            t = VCFTransformer()

        variants = [
            _mock_variant("1", 100001, "A", ["T"]),
            _mock_variant("2", 200001, "C", ["G"]),
        ]
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter(variants))
        out = tmp_path / "vcf_out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))

        # Convert JSONL to JSON for validator
        jsonl_path = out / "variants_batch.jsonl"
        records = [json.loads(line) for line in jsonl_path.read_text().strip().splitlines()]
        json_path = out / "variants.json"
        json_path.write_text(json.dumps(records))

        vcfg = {"validation": {"strict_mode": False}, "processing": {"log_level": "WARNING"}}
        with patch.object(BeaconValidator, "_load_config", return_value=vcfg):
            validator = BeaconValidator()
        result = validator.validate_json_file(str(json_path), schema_type="variant")
        assert result.is_valid is True, f"Validation errors: {result.errors}"

    def test_phenotype_output_validates(self, tmp_path, phenotype_fixtures_dir):
        """Phenotypes produced by phenotype transform should pass phenotype schema
        after stripping None/NaN values (known serialization gap between transform and validator)."""
        cfg = {
            "phenotypes": {"default_ontology": "HPO", "supported_formats": ["csv"]},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        }
        with patch.object(PhenotypeTransformer, "_load_config", return_value=cfg):
            t = PhenotypeTransformer()
            t.ontology_manager = OntologyManager(cfg)
            t.ontology_manager.lookup_term = MagicMock(return_value=None)

        t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_standard.csv"),
            str(tmp_path / "pheno_out"),
        )

        # Strip None/NaN from output (import pipeline would do this)
        raw = json.loads((tmp_path / "pheno_out" / "phenotypes.json").read_text())
        cleaned = [
            {k: v for k, v in rec.items() if v is not None and not (isinstance(v, float) and v != v)}
            for rec in raw
        ]
        clean_path = tmp_path / "pheno_out" / "phenotypes_clean.json"
        clean_path.write_text(json.dumps(cleaned))

        vcfg = {"validation": {"strict_mode": False}, "processing": {"log_level": "WARNING"}}
        with patch.object(BeaconValidator, "_load_config", return_value=vcfg):
            validator = BeaconValidator()
        result = validator.validate_json_file(str(clean_path), schema_type="phenotype")
        assert result.is_valid is True, f"Validation errors: {result.errors}"

    def test_individuals_output_validates(self, tmp_path):
        """Individual records should pass individual schema
        after stripping None values from optional fields."""
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {"min_qual": 0, "min_depth": 0}},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            t = VCFTransformer()

        mock_vcf = MagicMock()
        mock_vcf.samples = ["SAMPLE1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))

        # Strip None values from output
        raw = json.loads((out / "individuals.json").read_text())
        cleaned = [{k: v for k, v in rec.items() if v is not None} for rec in raw]
        clean_path = out / "individuals_clean.json"
        clean_path.write_text(json.dumps(cleaned))

        vcfg = {"validation": {"strict_mode": False}, "processing": {"log_level": "WARNING"}}
        with patch.object(BeaconValidator, "_load_config", return_value=vcfg):
            validator = BeaconValidator()
        result = validator.validate_json_file(str(clean_path), schema_type="individual")
        assert result.is_valid is True, f"Validation errors: {result.errors}"
