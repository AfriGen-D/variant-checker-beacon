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


class TestOutputOmitsUnknownFields:
    """Unknown optional fields are absent from the written records.

    The phenotype schema types age_of_onset and severity as strings and evidence as
    an object, none nullable, and a literal NaN is not valid JSON. A blank CSV cell
    reaches the transformer as NaN, and a row with no evidence columns produced
    evidence=None, so every phenotypes.json carried null and NaN until now.
    """

    def setup_method(self):
        self.t = _make_transformer()

    @staticmethod
    def _strict(path):
        def refuse(name):
            raise ValueError("non-standard JSON constant %r in %s" % (name, path))
        return json.loads(Path(path).read_text(), parse_constant=refuse)

    @staticmethod
    def _df_with_blanks():
        return pd.DataFrame({
            "individual_id": ["I1", "I2"],
            "phenotype_id": ["HP:0001250", "HP:0000252"],
            "phenotype_label": ["Seizures", "Microcephaly"],
            "ontology": ["HPO", "HPO"],
            "observed": [True, True],
            "age_of_onset": ["5y", float("nan")],
            "severity": [float("nan"), "Severe"],
            # transform_phenotype_file reads df["disease_id"] unconditionally, so a
            # file without that column fails; give it an all-blank one.
            "disease_id": [float("nan"), float("nan")],
        })

    def test_phenotype_to_dict_omits_unknown_fields(self):
        d = PhenotypeRecord(individual_id="I1", phenotype_id="HP:001",
                            phenotype_label="X", ontology="HPO").to_dict()
        assert None not in d.values()
        assert d["observed"] is True and d["modifiers"] == []
        for field in ("age_of_onset", "severity", "evidence"):
            assert field not in d

    def test_disease_to_dict_omits_unknown_fields_but_keeps_false(self):
        d = DiseaseRecord(individual_id="I1", disease_id="MONDO:001",
                          disease_label="X", ontology="MONDO").to_dict()
        assert None not in d.values()
        # False is a value, not an absence.
        assert d["family_history"] is False
        for field in ("age_of_onset", "stage", "notes"):
            assert field not in d

    def test_blank_cells_do_not_become_nan_in_records(self):
        records = self.t.transform_phenotypes(self._df_with_blanks())
        assert records[0].age_of_onset == "5y" and records[0].severity is None
        assert records[1].age_of_onset is None and records[1].severity == "Severe"

    def test_blank_disease_cells_do_not_become_nan_in_records(self):
        df = pd.DataFrame({
            "individual_id": ["I1"], "disease_id": ["MONDO:0005027"],
            "disease_label": ["Epilepsy"], "ontology": ["MONDO"],
            "age_of_onset": [float("nan")], "stage": [float("nan")],
            "notes": [float("nan")],
        })
        r = self.t.transform_diseases(df)[0]
        assert r.age_of_onset is None and r.stage is None and r.notes is None

    def test_written_phenotypes_are_strict_json_without_nulls(self, tmp_path):
        csv = tmp_path / "p.csv"
        self._df_with_blanks().to_csv(csv, index=False)
        self.t.transform_phenotype_file(str(csv), str(tmp_path / "out"))
        recs = self._strict(tmp_path / "out" / "phenotypes.json")
        assert len(recs) == 2
        for rec in recs:
            assert None not in rec.values(), rec
        assert recs[0]["age_of_onset"] == "5y" and "severity" not in recs[0]
        assert recs[1]["severity"] == "Severe" and "age_of_onset" not in recs[1]

    def test_every_written_file_is_strict_json_for_the_standard_fixture(self, tmp_path):
        fixtures = Path(__file__).resolve().parents[1] / "fixtures"
        out = tmp_path / "out"
        self.t.transform_phenotype_file(
            str(fixtures / "phenotype" / "phenotypes_standard.csv"), str(out),
            individuals_file=str(fixtures / "json" / "valid_individuals.json"))
        for name in ("phenotypes.json", "diseases.json", "individuals_with_phenotypes.json"):
            data = self._strict(out / name)
            assert data, name
        for rec in self._strict(out / "phenotypes.json") + self._strict(out / "diseases.json"):
            assert None not in rec.values(), rec


class TestFilesWithOnlyOneKindOfData:
    """A file may carry phenotypes or diseases or both.

    The guide marks phenotype_id "for phenotypes" and disease_id "for diseases",
    so neither column is required. Both transforms used to read their column
    unconditionally, so a phenotype-only file died with KeyError: 'disease_id' and
    a disease-only file with KeyError: 'phenotype_id'.
    """

    def setup_method(self):
        self.t = _make_transformer()

    def test_no_disease_column_means_no_disease_records(self):
        df = _standard_df()
        assert "disease_id" not in df.columns
        assert self.t.transform_diseases(df) == []

    def test_no_phenotype_column_means_no_phenotype_records(self):
        df = pd.DataFrame({
            "individual_id": ["I1"], "disease_id": ["MONDO:0005027"],
            "disease_label": ["Epilepsy"], "ontology": ["MONDO"],
        })
        assert "phenotype_id" not in df.columns
        assert self.t.transform_phenotypes(df) == []

    def test_empty_dataframe_with_neither_column(self):
        df = pd.DataFrame({"individual_id": ["I1"]})
        assert self.t.transform_phenotypes(df) == []
        assert self.t.transform_diseases(df) == []

    def test_phenotype_only_file_is_written(self, tmp_path):
        csv = tmp_path / "p.csv"
        _standard_df().to_csv(csv, index=False)
        out = tmp_path / "out"
        self.t.transform_phenotype_file(str(csv), str(out))
        assert len(json.loads((out / "phenotypes.json").read_text())) == 2
        assert json.loads((out / "diseases.json").read_text()) == []

    def test_disease_only_file_is_written(self, tmp_path):
        csv = tmp_path / "d.csv"
        pd.DataFrame({
            "individual_id": ["I1"], "disease_id": ["MONDO:0005027"],
            "disease_label": ["Epilepsy"], "ontology": ["MONDO"],
        }).to_csv(csv, index=False)
        out = tmp_path / "out"
        self.t.transform_phenotype_file(str(csv), str(out))
        assert json.loads((out / "phenotypes.json").read_text()) == []
        assert len(json.loads((out / "diseases.json").read_text())) == 1

    def test_a_file_with_both_still_works(self, tmp_path):
        # Control: the fixture the guide's Step 5 shows, with both kinds.
        fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "phenotype"
        out = tmp_path / "out"
        self.t.transform_phenotype_file(str(fixtures / "phenotypes_standard.csv"), str(out))
        assert json.loads((out / "phenotypes.json").read_text())
        assert json.loads((out / "diseases.json").read_text())
