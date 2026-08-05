"""Unit tests for vcf_transform.vcf_to_beacon — highest-risk logic."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Patch heavy C-extension imports before importing the module under test.
# ---------------------------------------------------------------------------
_STUBS = {}
for mod_name in ("cyvcf2", "pysam", "biopython", "biopython.SeqIO", "Bio", "Bio.SeqIO"):
    if mod_name not in sys.modules:
        _STUBS[mod_name] = MagicMock()
        sys.modules[mod_name] = _STUBS[mod_name]

from vcf_transform.vcf_to_beacon import (  # noqa: E402
    VCFTransformer,
    VariantRecord,
    IndividualRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transformer(**config_overrides) -> VCFTransformer:
    """Build a VCFTransformer with a patched config (no file I/O)."""
    cfg = {
        "vcf": {"default_assembly": "GRCh38", "quality_filters": {"min_qual": 20, "min_depth": 10}},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    cfg.update(config_overrides)
    with patch.object(VCFTransformer, "_load_config", return_value=cfg):
        return VCFTransformer()


def _make_variant(chrom="1", pos=100001, ref="A", alt=None, qual=30.0,
                  info=None, genotypes=None, filter_val=None):
    """Build a lightweight mock cyvcf2 Variant."""
    v = MagicMock()
    v.CHROM = chrom
    v.POS = pos
    v.REF = ref
    v.ALT = alt or ["T"]
    v.QUAL = qual
    v.FILTER = filter_val
    v.INFO = info if info is not None else {}
    v.genotypes = genotypes or [[0, 1, False]]
    v.format.return_value = {}
    return v


# ===================================================================
# TestDetermineVariantType
# ===================================================================

class TestDetermineVariantType:
    """Verify REF/ALT → variant-type classification."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_snv(self):
        assert self.t._determine_variant_type("A", ["T"]) == "SNV"

    def test_deletion(self):
        assert self.t._determine_variant_type("ATG", ["A"]) == "DEL"

    def test_insertion(self):
        assert self.t._determine_variant_type("A", ["ATCG"]) == "INS"

    def test_complex(self):
        assert self.t._determine_variant_type("AT", ["GC"]) == "COMPLEX"

    def test_no_alt_returns_unknown(self):
        assert self.t._determine_variant_type("A", [None]) == "unknown"

    def test_empty_alt_list(self):
        assert self.t._determine_variant_type("A", []) == "unknown"


# ===================================================================
# TestCreateVariantRecord
# ===================================================================

class TestCreateVariantRecord:
    """Verify VariantRecord creation — especially 0-based coordinate conversion."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_start_is_zero_based(self):
        """POS 100001 (1-based VCF) → start 100000 (0-based Beacon)."""
        v = _make_variant(pos=100001)
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.start == 100000

    def test_end_calculation_snv(self):
        """End for SNV: start + len(REF) = 100000 + 1 = 100001."""
        v = _make_variant(pos=100001, ref="A", alt=["T"])
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.end == 100001

    def test_end_calculation_deletion(self):
        """End for DEL(ATG→A): start + 3 = 100003."""
        v = _make_variant(pos=100001, ref="ATG", alt=["A"])
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.end == 100003

    def test_id_format(self):
        v = _make_variant(chrom="2", pos=500, ref="C", alt=["G"])
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.id == "2:500:C:G"

    def test_assembly_stored(self):
        v = _make_variant()
        rec = self.t._create_variant_record(v, "GRCh37")
        assert rec.assembly_id == "GRCh37"

    def test_reference_name_is_string(self):
        v = _make_variant(chrom=1)
        rec = self.t._create_variant_record(v, "GRCh38")
        assert isinstance(rec.reference_name, str)

    def test_variant_type_set(self):
        v = _make_variant(ref="A", alt=["ATCG"])
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.variant_type == "INS"

    def test_allele_frequency_extracted(self):
        """AF in INFO is captured into the queryable allele_frequency field."""
        v = _make_variant(info={"AF": 0.5})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency == 0.5

    def test_allele_frequency_tuple_takes_first(self):
        """Multi-allelic AF (tuple) → first ALT allele's frequency."""
        v = _make_variant(info={"AF": (0.33, 0.01)})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency == 0.33

    def test_allele_frequency_absent_is_none(self):
        """No AF in INFO → allele_frequency stays None (no fabricated value)."""
        v = _make_variant(info={"DP": 50})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency is None


# ===================================================================
# TestPassesQualityFilters
# ===================================================================

class TestPassesQualityFilters:
    """Verify QUAL ≥ 20 and DP ≥ 10 threshold logic."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_passes_both(self):
        v = _make_variant(qual=30, info={"DP": 20})
        assert self.t._passes_quality_filters(v) is True

    def test_fails_low_qual(self):
        v = _make_variant(qual=5)
        assert self.t._passes_quality_filters(v) is False

    def test_fails_low_depth(self):
        v = _make_variant(qual=30, info={"DP": 5})
        assert self.t._passes_quality_filters(v) is False

    def test_boundary_qual_exact(self):
        """QUAL == 20 should pass (filter is <, not <=)."""
        v = _make_variant(qual=20, info={"DP": 20})
        assert self.t._passes_quality_filters(v) is True

    def test_boundary_qual_just_below(self):
        v = _make_variant(qual=19.9, info={"DP": 20})
        assert self.t._passes_quality_filters(v) is False

    def test_boundary_depth_exact(self):
        v = _make_variant(qual=30, info={"DP": 10})
        assert self.t._passes_quality_filters(v) is True

    def test_qual_none_passes(self):
        """Missing QUAL (None) should not fail the filter."""
        v = _make_variant(qual=None)
        assert self.t._passes_quality_filters(v) is True

    def test_no_dp_in_info(self):
        """Missing DP in INFO should still pass."""
        v = _make_variant(qual=30, info={})
        assert self.t._passes_quality_filters(v) is True


# ===================================================================
# TestExtractAnnotations
# ===================================================================

class TestExtractAnnotations:
    """Verify VEP/SnpEff/basic annotation extraction from INFO."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_empty_info(self):
        v = _make_variant(info={})
        anns = self.t._extract_annotations(v)
        assert anns == []

    def test_vep_csq_parsed(self):
        v = _make_variant(info={"CSQ": ["missense_variant|BRCA1"]})
        anns = self.t._extract_annotations(v)
        vep = [a for a in anns if a.get("source") == "VEP"]
        assert len(vep) == 1
        assert "missense_variant" in vep[0]["consequence"]

    def test_snpeff_ann_parsed(self):
        v = _make_variant(info={"ANN": ["frameshift_variant|HIGH"]})
        anns = self.t._extract_annotations(v)
        snpeff = [a for a in anns if a.get("source") == "SnpEff"]
        assert len(snpeff) == 1

    def test_basic_info_fields(self):
        v = _make_variant(info={"GENE": "BRCA1", "AF": 0.5})
        anns = self.t._extract_annotations(v)
        info_ann = [a for a in anns if a.get("source") == "INFO"]
        assert len(info_ann) == 1
        assert info_ann[0]["annotations"]["gene"] == "BRCA1"

    def test_no_info_attribute(self):
        """Variant without INFO attr returns empty list."""
        v = MagicMock(spec=[])  # no attributes at all
        anns = self.t._extract_annotations(v)
        assert anns == []


# ===================================================================
# TestExtractAlleleFrequency
# ===================================================================

class TestExtractAlleleFrequency:
    """Verify AF extraction from INFO — the value served at aggregated granularity."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_float_af(self):
        v = _make_variant(info={"AF": 0.0423})
        assert self.t._extract_allele_frequency(v) == pytest.approx(0.0423)

    def test_string_af_is_coerced(self):
        """Some writers emit AF as a string; it must still land as a float."""
        v = _make_variant(info={"AF": "0.25"})
        assert self.t._extract_allele_frequency(v) == pytest.approx(0.25)

    def test_missing_af_returns_none(self):
        v = _make_variant(info={})
        assert self.t._extract_allele_frequency(v) is None

    def test_no_info_attribute_returns_none(self):
        v = MagicMock(spec=[])
        assert self.t._extract_allele_frequency(v) is None

    def test_multiallelic_af_takes_first_alt(self):
        """
        A multi-allelic site carries one AF per ALT. Only ALT[0]'s frequency is
        kept, while alternate_bases is written as the joined "T,G" string — so
        the retained AF describes an allele that cannot itself be queried.
        This pins current behaviour; splitting multi-allelics at ingest is the
        real fix.
        """
        v = _make_variant(info={"AF": (0.1, 0.9)})
        assert self.t._extract_allele_frequency(v) == pytest.approx(0.1)

    def test_empty_af_sequence_returns_none(self):
        v = _make_variant(info={"AF": []})
        assert self.t._extract_allele_frequency(v) is None

    def test_non_numeric_af_returns_none(self):
        v = _make_variant(info={"AF": "not-a-number"})
        assert self.t._extract_allele_frequency(v) is None

    def test_af_reaches_the_variant_record(self):
        v = _make_variant(info={"AF": 0.31})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency == pytest.approx(0.31)

    def test_record_af_is_none_when_absent(self):
        v = _make_variant(info={})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency is None


# ===================================================================
# TestParseAnnotationHelpers
# ===================================================================

class TestParseAnnotationHelpers:
    """Verify the VEP/SnpEff parsers, including non-list inputs."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_vep_non_list_yields_nothing(self):
        assert self.t._parse_vep_annotations("missense_variant|BRCA1") == []

    def test_vep_list_yields_one_per_entry(self):
        anns = self.t._parse_vep_annotations(["a|1", "b|2"])
        assert [a["source"] for a in anns] == ["VEP", "VEP"]
        assert anns[1]["consequence"] == "b|2"

    def test_snpeff_non_list_yields_nothing(self):
        assert self.t._parse_snpeff_annotations("frameshift|HIGH") == []

    def test_snpeff_list_yields_one_per_entry(self):
        anns = self.t._parse_snpeff_annotations(["x|HIGH", "y|LOW"])
        assert [a["source"] for a in anns] == ["SnpEff", "SnpEff"]
        assert anns[0]["annotation"] == "x|HIGH"


# ===================================================================
# TestExtractGenotypeInfo
# ===================================================================

class TestExtractGenotypeInfo:
    """Verify genotype parsing for various GT patterns."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_heterozygous(self):
        v = _make_variant(genotypes=[[0, 1, False]])
        info = self.t._extract_genotype_info(v, 0)
        assert info["alleles"] == [0, 1]
        assert info["phased"] is False

    def test_homozygous_alt(self):
        v = _make_variant(genotypes=[[1, 1, False]])
        info = self.t._extract_genotype_info(v, 0)
        assert info["alleles"] == [1, 1]

    def test_homozygous_ref(self):
        v = _make_variant(genotypes=[[0, 0, False]])
        info = self.t._extract_genotype_info(v, 0)
        assert info["alleles"] == [0, 0]

    def test_phased(self):
        v = _make_variant(genotypes=[[0, 1, True]])
        info = self.t._extract_genotype_info(v, 0)
        assert info["phased"] is True

    def test_missing_genotype_returns_none(self):
        v = _make_variant(genotypes=[[-1, -1, False]])
        info = self.t._extract_genotype_info(v, 0)
        assert info is None

    def test_multi_sample_second_index(self):
        v = _make_variant(genotypes=[[0, 0, False], [1, 1, False]])
        info = self.t._extract_genotype_info(v, 1)
        assert info["alleles"] == [1, 1]

    def test_out_of_range_index(self):
        v = _make_variant(genotypes=[[0, 1, False]])
        info = self.t._extract_genotype_info(v, 5)
        assert info is None

    def test_format_dp_extracted(self):
        # cyvcf2's variant.format(field) takes the field name and returns a
        # per-sample array indexed [sample_idx][0] — not a dict keyed by field.
        # Absent fields come back as None.
        v = _make_variant(genotypes=[[0, 1, False]])
        v.format.side_effect = lambda f: {"DP": [[50]]}.get(f)
        info = self.t._extract_genotype_info(v, 0)
        assert info["depth"] == 50

    def test_format_gq_extracted(self):
        v = _make_variant(genotypes=[[0, 1, False]])
        v.format.side_effect = lambda f: {"GQ": [[99]]}.get(f)
        info = self.t._extract_genotype_info(v, 0)
        assert info["quality"] == 99


# ===================================================================
# TestTransformVcfToBeacon (end-to-end with mocked cyvcf2)
# ===================================================================

class TestTransformVcfToBeacon:
    """Integration-ish tests using mocked cyvcf2 for the full transform pipeline."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_output_dir_created(self, tmp_path):
        out = tmp_path / "beacon_out"
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert out.exists()

    def test_summary_file_created(self, tmp_path):
        out = tmp_path / "out"
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            summary = self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert "transformation_summary.json" in [
            f.name for f in out.iterdir()
        ]
        assert "statistics" in summary

    def test_variants_written_as_jsonl(self, tmp_path):
        out = tmp_path / "out"
        v = _make_variant(pos=100, ref="A", alt=["T"], qual=30, info={"DP": 20})
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([v]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        jsonl = out / "variants_batch.jsonl"
        assert jsonl.exists()
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) >= 1
        rec = json.loads(lines[0])
        assert rec["start"] == 99  # 0-based

    def test_individuals_json_created(self, tmp_path):
        out = tmp_path / "out"
        mock_vcf = MagicMock()
        mock_vcf.samples = ["SAMPLE_A", "SAMPLE_B"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        ind_file = out / "individuals.json"
        assert ind_file.exists()
        data = json.loads(ind_file.read_text())
        assert len(data) == 2

    def test_empty_vcf_produces_empty_output(self, tmp_path):
        out = tmp_path / "out"
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            summary = self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert summary["statistics"]["variants_processed"] == 0


# ===================================================================
# TestVariantRecord dataclass
# ===================================================================

class TestVariantRecordDataclass:
    """Verify VariantRecord defaults and post_init."""

    def test_defaults_set(self):
        r = VariantRecord(
            id="test", assembly_id="GRCh38", reference_name="1",
            start=0, end=1, reference_bases="A",
            alternate_bases="T", variant_type="SNV",
        )
        assert r.created is not None
        assert r.updated is not None
        assert r.annotations == []

    def test_annotations_preserved_when_given(self):
        r = VariantRecord(
            id="test", assembly_id="GRCh38", reference_name="1",
            start=0, end=1, reference_bases="A",
            alternate_bases="T", variant_type="SNV",
            annotations=[{"source": "VEP"}],
        )
        assert len(r.annotations) == 1


# ===================================================================
# TestIndividualRecord dataclass
# ===================================================================

class TestIndividualRecordDataclass:
    def test_defaults_set(self):
        r = IndividualRecord(id="IND001")
        assert r.created is not None
        assert r.diseases == {}
        assert r.phenotypic_features == {}

    def test_optional_fields(self):
        r = IndividualRecord(id="IND001", sex="MALE", age=30, ethnicity="African")
        assert r.sex == "MALE"
        assert r.age == 30
