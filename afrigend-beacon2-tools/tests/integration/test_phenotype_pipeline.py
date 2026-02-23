"""Integration tests for phenotype → Beacon pipeline."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

if "pronto" not in sys.modules:
    sys.modules["pronto"] = MagicMock()

from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer, OntologyManager


def _make_transformer():
    cfg = {
        "phenotypes": {"default_ontology": "HPO", "supported_formats": ["csv", "tsv", "xlsx", "json"]},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    with patch.object(PhenotypeTransformer, "_load_config", return_value=cfg):
        t = PhenotypeTransformer()
        t.ontology_manager = OntologyManager(cfg)
        t.ontology_manager.lookup_term = MagicMock(return_value=None)
        return t


@pytest.mark.integration
class TestPhenotypePipeline:
    def test_standard_csv_end_to_end(self, tmp_path, phenotype_fixtures_dir):
        t = _make_transformer()
        summary = t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_standard.csv"),
            str(tmp_path / "output"),
        )
        assert (tmp_path / "output" / "phenotypes.json").exists()
        assert (tmp_path / "output" / "diseases.json").exists()
        assert summary["statistics"]["phenotypes_processed"] >= 1

    def test_flexible_columns_normalized(self, tmp_path, phenotype_fixtures_dir):
        t = _make_transformer()
        summary = t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_flexible.csv"),
            str(tmp_path / "output"),
        )
        phenotypes = json.loads((tmp_path / "output" / "phenotypes.json").read_text())
        assert len(phenotypes) >= 3
        assert all(p["individual_id"] for p in phenotypes)

    def test_diseases_extracted(self, tmp_path, phenotype_fixtures_dir):
        t = _make_transformer()
        t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_diseases.csv"),
            str(tmp_path / "output"),
        )
        diseases = json.loads((tmp_path / "output" / "diseases.json").read_text())
        assert len(diseases) >= 3

    def test_individuals_updated(self, tmp_path, phenotype_fixtures_dir, json_fixtures_dir):
        t = _make_transformer()
        t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_standard.csv"),
            str(tmp_path / "output"),
            individuals_file=str(json_fixtures_dir / "valid_individuals.json"),
        )
        updated = tmp_path / "output" / "individuals_with_phenotypes.json"
        assert updated.exists()
        data = json.loads(updated.read_text())
        ind1 = next((i for i in data if i["id"] == "IND001"), None)
        assert ind1 is not None
        assert "phenotypic_features" in ind1

    def test_summary_file(self, tmp_path, phenotype_fixtures_dir):
        t = _make_transformer()
        t.transform_phenotype_file(
            str(phenotype_fixtures_dir / "phenotypes_standard.csv"),
            str(tmp_path / "output"),
        )
        summary_file = tmp_path / "output" / "phenotype_transformation_summary.json"
        assert summary_file.exists()
