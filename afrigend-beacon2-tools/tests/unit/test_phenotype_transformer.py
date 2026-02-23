"""Unit tests for phenotype_transform.phenotype_to_beacon."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd
import numpy as np

# Patch pronto before import
if "pronto" not in sys.modules:
    sys.modules["pronto"] = MagicMock()

from phenotype_transform.phenotype_to_beacon import (  # noqa: E402
    PhenotypeTransformer,
    PhenotypeRecord,
    DiseaseRecord,
    OntologyManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transformer(**cfg_overrides) -> PhenotypeTransformer:
    cfg = {
        "phenotypes": {"default_ontology": "HPO", "supported_formats": ["csv", "tsv", "xlsx", "json"]},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    cfg.update(cfg_overrides)
    with patch.object(PhenotypeTransformer, "_load_config", return_value=cfg):
        t = PhenotypeTransformer()
        # Replace ontology manager with non-network version
        t.ontology_manager = OntologyManager(cfg)
        t.ontology_manager.lookup_term = MagicMock(return_value=None)
        return t


def _standard_df():
    return pd.DataFrame({
        "individual_id": ["IND001", "IND002"],
        "phenotype_id": ["HP:0001250", "HP:0000252"],
        "phenotype_label": ["Seizures", "Microcephaly"],
        "ontology": ["HPO", "HPO"],
        "observed": [True, True],
    })


# ===================================================================
# TestNormalizePhenotypeData
# ===================================================================

class TestNormalizePhenotypeData:
    def setup_method(self):
        self.t = _make_transformer()

    # --- Column mapping tests ---
    def test_standard_columns_unchanged(self):
        df = _standard_df()
        result = self.t.normalize_phenotype_data(df)
        assert "individual_id" in result.columns
        assert "phenotype_id" in result.columns

    def test_patient_id_mapped(self):
        df = pd.DataFrame({"patient_id": ["P1"], "phenotype_id": ["HP:001"], "phenotype_label": ["X"], "ontology": ["HPO"]})
        result = self.t.normalize_phenotype_data(df)
        assert "individual_id" in result.columns
        assert result["individual_id"].iloc[0] == "P1"

    def test_sample_id_mapped(self):
        df = pd.DataFrame({"sample_id": ["S1"], "phenotype_id": ["HP:001"], "phenotype_label": ["X"], "ontology": ["HPO"]})
        result = self.t.normalize_phenotype_data(df)
        assert "individual_id" in result.columns

    def test_hpo_id_mapped(self):
        df = pd.DataFrame({"individual_id": ["I1"], "hpo_id": ["HP:001"], "phenotype_label": ["X"], "ontology": ["HPO"]})
        result = self.t.normalize_phenotype_data(df)
        assert "phenotype_id" in result.columns
        assert result["phenotype_id"].iloc[0] == "HP:001"

    def test_term_name_mapped_to_label(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"], "term_name": ["Seizures"], "ontology": ["HPO"]})
        result = self.t.normalize_phenotype_data(df)
        assert "phenotype_label" in result.columns
        assert result["phenotype_label"].iloc[0] == "Seizures"

    def test_mondo_id_mapped_to_disease_id(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"], "phenotype_label": ["X"],
                          "ontology": ["HPO"], "mondo_id": ["MONDO:001"]})
        result = self.t.normalize_phenotype_data(df)
        assert "disease_id" in result.columns

    def test_diagnosis_mapped_to_disease_label(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"], "phenotype_label": ["X"],
                          "ontology": ["HPO"], "diagnosis": ["Epilepsy"]})
        result = self.t.normalize_phenotype_data(df)
        assert "disease_label" in result.columns

    # --- Boolean conversion tests ---
    def test_bool_true_string(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["true"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] is True or result["observed"].iloc[0] == True  # noqa: E712

    def test_bool_yes(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["yes"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == True  # noqa: E712

    def test_bool_present(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["present"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == True  # noqa: E712

    def test_bool_false_string(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["false"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == False  # noqa: E712

    def test_bool_no(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["no"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == False  # noqa: E712

    def test_bool_absent(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["absent"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == False  # noqa: E712

    def test_bool_numeric_1(self):
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": [1]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == True  # noqa: E712

    def test_bool_unknown_defaults_true(self):
        """Unknown boolean values should default to True per fillna(True)."""
        df = pd.DataFrame({"individual_id": ["I1"], "phenotype_id": ["HP:001"],
                          "phenotype_label": ["X"], "ontology": ["HPO"], "observed": ["maybe"]})
        result = self.t.normalize_phenotype_data(df)
        assert result["observed"].iloc[0] == True  # noqa: E712


# ===================================================================
# TestTransformPhenotypes
# ===================================================================

class TestTransformPhenotypes:
    def setup_method(self):
        self.t = _make_transformer()

    def test_creates_records(self):
        df = _standard_df()
        records = self.t.transform_phenotypes(df)
        assert len(records) == 2

    def test_record_fields(self):
        df = _standard_df()
        records = self.t.transform_phenotypes(df)
        r = records[0]
        assert isinstance(r, PhenotypeRecord)
        assert r.individual_id == "IND001"
        assert r.phenotype_id == "HP:0001250"

    def test_skips_nan_phenotype_id(self):
        df = pd.DataFrame({
            "individual_id": ["I1", "I2"],
            "phenotype_id": ["HP:001", float("nan")],
            "phenotype_label": ["X", "Y"],
            "ontology": ["HPO", "HPO"],
        })
        records = self.t.transform_phenotypes(df)
        assert len(records) == 1

    def test_stats_updated(self):
        df = _standard_df()
        self.t.transform_phenotypes(df)
        assert self.t.stats["phenotypes_processed"] == 2


# ===================================================================
# TestTransformDiseases
# ===================================================================

class TestTransformDiseases:
    def setup_method(self):
        self.t = _make_transformer()

    def test_creates_disease_records(self):
        df = pd.DataFrame({
            "individual_id": ["I1"],
            "disease_id": ["MONDO:0005027"],
            "disease_label": ["Epilepsy"],
            "ontology": ["MONDO"],
        })
        records = self.t.transform_diseases(df)
        assert len(records) == 1
        assert isinstance(records[0], DiseaseRecord)

    def test_disease_fields(self):
        df = pd.DataFrame({
            "individual_id": ["I1"],
            "disease_id": ["MONDO:0005027"],
            "disease_label": ["Epilepsy"],
            "ontology": ["MONDO"],
            "age_of_onset": ["5y"],
            "stage": ["early"],
            "family_history": [True],
            "notes": ["Family history"],
        })
        records = self.t.transform_diseases(df)
        r = records[0]
        assert r.age_of_onset == "5y"
        assert r.family_history is True

    def test_skips_nan_disease_id(self):
        df = pd.DataFrame({
            "individual_id": ["I1", "I2"],
            "disease_id": ["MONDO:001", float("nan")],
            "disease_label": ["X", "Y"],
            "ontology": ["MONDO", "MONDO"],
        })
        records = self.t.transform_diseases(df)
        assert len(records) == 1

    def test_default_ontology_is_mondo(self):
        df = pd.DataFrame({
            "individual_id": ["I1"],
            "disease_id": ["MONDO:001"],
            "disease_label": ["X"],
        })
        # ontology column missing → uses default 'MONDO' in transform_diseases
        df["ontology"] = float("nan")
        records = self.t.transform_diseases(df)
        # disease_id still set, ontology falls back to default
        assert len(records) == 1

    def test_stats_updated(self):
        df = pd.DataFrame({
            "individual_id": ["I1"],
            "disease_id": ["MONDO:001"],
            "disease_label": ["X"],
            "ontology": ["MONDO"],
        })
        self.t.transform_diseases(df)
        assert self.t.stats["diseases_processed"] == 1


# ===================================================================
# TestParseListField
# ===================================================================

class TestParseListField:
    def setup_method(self):
        self.t = _make_transformer()

    def test_none_returns_empty(self):
        assert self.t._parse_list_field(None) == []

    def test_nan_returns_empty(self):
        assert self.t._parse_list_field(float("nan")) == []

    def test_list_passed_through(self):
        assert self.t._parse_list_field(["a", "b"]) == ["a", "b"]

    def test_comma_string_split(self):
        assert self.t._parse_list_field("a, b, c") == ["a", "b", "c"]

    def test_single_value_wrapped(self):
        assert self.t._parse_list_field(42) == ["42"]


# ===================================================================
# TestUpdateIndividualsWithPhenotypes
# ===================================================================

class TestUpdateIndividualsWithPhenotypes:
    def setup_method(self):
        self.t = _make_transformer()

    def test_phenotypes_attached(self):
        individuals = [{"id": "IND001"}]
        phenotypes = [PhenotypeRecord(
            individual_id="IND001", phenotype_id="HP:001",
            phenotype_label="Seizures", ontology="HPO",
        )]
        result = self.t.update_individuals_with_phenotypes(individuals, phenotypes, [])
        assert "phenotypic_features" in result[0]
        assert len(result[0]["phenotypic_features"]) == 1

    def test_diseases_attached(self):
        individuals = [{"id": "IND001"}]
        diseases = [DiseaseRecord(
            individual_id="IND001", disease_id="MONDO:001",
            disease_label="Epilepsy", ontology="MONDO",
        )]
        result = self.t.update_individuals_with_phenotypes(individuals, [], diseases)
        assert "diseases" in result[0]
        assert len(result[0]["diseases"]) == 1

    def test_no_match_leaves_individual_unchanged(self):
        individuals = [{"id": "IND999"}]
        phenotypes = [PhenotypeRecord(
            individual_id="IND001", phenotype_id="HP:001",
            phenotype_label="X", ontology="HPO",
        )]
        result = self.t.update_individuals_with_phenotypes(individuals, phenotypes, [])
        assert "phenotypic_features" not in result[0]

    def test_multiple_phenotypes_same_individual(self):
        individuals = [{"id": "IND001"}]
        phenotypes = [
            PhenotypeRecord(individual_id="IND001", phenotype_id="HP:001",
                          phenotype_label="X", ontology="HPO"),
            PhenotypeRecord(individual_id="IND001", phenotype_id="HP:002",
                          phenotype_label="Y", ontology="HPO"),
        ]
        result = self.t.update_individuals_with_phenotypes(individuals, phenotypes, [])
        assert len(result[0]["phenotypic_features"]) == 2

    def test_individual_id_fallback(self):
        """Should also work when individual uses 'individual_id' key."""
        individuals = [{"individual_id": "IND001"}]
        phenotypes = [PhenotypeRecord(
            individual_id="IND001", phenotype_id="HP:001",
            phenotype_label="X", ontology="HPO",
        )]
        result = self.t.update_individuals_with_phenotypes(individuals, phenotypes, [])
        assert "phenotypic_features" in result[0]


# ===================================================================
# TestOntologyManager
# ===================================================================

class TestOntologyManager:
    def _make_manager(self):
        cfg = {"phenotypes": {"default_ontology": "HPO"}}
        return OntologyManager(cfg)

    def test_infer_hpo(self):
        m = self._make_manager()
        assert m._infer_ontology_from_id("HP:0001250") == "HPO"

    def test_infer_mondo(self):
        m = self._make_manager()
        assert m._infer_ontology_from_id("MONDO:0005027") == "MONDO"

    def test_infer_ordo(self):
        m = self._make_manager()
        assert m._infer_ontology_from_id("ORDO:123") == "ORDO"

    def test_infer_ncit(self):
        m = self._make_manager()
        assert m._infer_ontology_from_id("NCIT:C1234") == "NCIT"

    def test_infer_unknown(self):
        m = self._make_manager()
        assert m._infer_ontology_from_id("UNKNOWN:123") is None

    def test_cache_hit(self):
        m = self._make_manager()
        m.cache["HPO:HP:001"] = {"id": "HP:001", "label": "cached"}
        result = m.lookup_term("HP:001", "HPO")
        assert result["label"] == "cached"

    @patch("phenotype_transform.phenotype_to_beacon.requests.get")
    def test_api_fallback_called(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        m = self._make_manager()
        # No ontology loaded → falls to API
        result = m.lookup_term("HP:9999999", "HPO")
        assert result is None  # 404 returns None

    @patch("phenotype_transform.phenotype_to_beacon.requests.get")
    def test_api_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"id": "HP:001", "name": "Seizures",
                                         "definition": "def", "synonyms": [],
                                         "isObsolete": False}),
        )
        m = self._make_manager()
        result = m._api_lookup("HP:001", "HPO")
        assert result["label"] == "Seizures"


# ===================================================================
# TestPhenotypeRecord / DiseaseRecord dataclasses
# ===================================================================

class TestPhenotypeRecordDataclass:
    def test_defaults(self):
        r = PhenotypeRecord(individual_id="I1", phenotype_id="HP:001",
                           phenotype_label="X", ontology="HPO")
        assert r.observed is True
        assert r.modifiers == []
        assert r.created is not None

    def test_optional_fields(self):
        r = PhenotypeRecord(
            individual_id="I1", phenotype_id="HP:001",
            phenotype_label="X", ontology="HPO",
            age_of_onset="5y", severity="Severe",
        )
        assert r.age_of_onset == "5y"


class TestDiseaseRecordDataclass:
    def test_defaults(self):
        r = DiseaseRecord(individual_id="I1", disease_id="MONDO:001",
                         disease_label="X", ontology="MONDO")
        assert r.family_history is False
        assert r.created is not None
