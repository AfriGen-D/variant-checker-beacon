"""Unit tests for vcf_transform.vcf_to_beacon — highest-risk logic."""
import json
import logging
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


class FakeInfo:
    """Stand-in for cyvcf2's INFO object.

    Deliberately mirrors the real API rather than a dict: it exposes `.get()`
    and `[]`, and iterates as (key, value) tuples with **no** `__contains__` —
    which is exactly why `'CSQ' in variant.INFO` silently evaluated False on
    real VCFs. A dict here would let that bug pass the suite.
    """

    def __init__(self, data: dict = None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data.items())


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
    v.INFO = FakeInfo(info)
    v.genotypes = genotypes or [[0, 1, False]]
    v.format.return_value = {}
    return v


class FakeVCF:
    """Stand-in for cyvcf2.VCF: iterable of variants plus header accessors."""

    def __init__(self, variants=None, samples=None, header_types=None, raw_header=""):
        self._variants = list(variants or [])
        self.samples = samples or ["S1"]
        self._header_types = dict(header_types or {})
        self.raw_header = raw_header

    def get_header_type(self, key):
        # cyvcf2 raises KeyError for an INFO id the header does not declare.
        return self._header_types[key]

    def __iter__(self):
        return iter(self._variants)


# VEP writes its column order into the CSQ header line; it varies per run.
VEP_CSQ_DESCRIPTION = (
    '"Consequence annotations from Ensembl VEP. Format: '
    'Allele|Consequence|IMPACT|SYMBOL|Gene|Feature_type|Feature|BIOTYPE|CLIN_SIG|ALLELE_NUM"'
)
SNPEFF_ANN_DESCRIPTION = (
    '"Functional annotations: \'Allele | Annotation | Annotation_Impact | '
    'Gene_Name | Gene_ID | Feature_Type | Feature_ID | Transcript_BioType | Rank | '
    'HGVS.c | HGVS.p | cDNA.pos / cDNA.length | CDS.pos / CDS.length | '
    'AA.pos / AA.length | Distance | ERRORS / WARNINGS / INFO\'"'
)


def _run_parse(transformer, variants, vcf=None):
    """Drive parse_vcf over a FakeVCF and collect the emitted records."""
    fake = vcf if vcf is not None else FakeVCF(variants)
    with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=fake):
        return list(transformer.parse_vcf("fake.vcf", "GRCh38"))


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

    def test_allele_frequency_tuple_indexed_by_alt(self):
        """Multi-allelic AF (tuple) → the frequency of the ALT being emitted."""
        v = _make_variant(alt=["T", "G"], info={"AF": (0.33, 0.01)})
        assert self.t._create_variant_record(v, "GRCh38", 0).allele_frequency == 0.33
        assert self.t._create_variant_record(v, "GRCh38", 1).allele_frequency == 0.01

    def test_allele_frequency_absent_is_none(self):
        """No AF in INFO → allele_frequency stays None (no fabricated value)."""
        v = _make_variant(info={"DP": 50})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.allele_frequency is None


# ===================================================================
# TestMultiAllelicSplit
# ===================================================================

class TestMultiAllelicSplit:
    """A multi-allelic site must become one queryable record per ALT allele."""

    def setup_method(self):
        self.t = _make_transformer()

    def _records(self, variant):
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([variant]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            return list(self.t.parse_vcf("fake.vcf", "GRCh38"))

    def test_one_record_per_alt(self):
        v = _make_variant(chrom="1", pos=100, ref="A", alt=["T", "G"], info={"DP": 20})
        recs = self._records(v)
        assert [r.alternate_bases for r in recs] == ["T", "G"]

    def test_no_joined_allele_string(self):
        """The unqueryable "T,G" form must not be emitted at all."""
        v = _make_variant(alt=["T", "G"], info={"DP": 20})
        assert all("," not in r.alternate_bases for r in self._records(v))

    def test_ids_unique_per_allele(self):
        v = _make_variant(chrom="2", pos=500, ref="C", alt=["G", "T"], info={"DP": 20})
        ids = [r.id for r in self._records(v)]
        assert ids == ["2:500:C:G", "2:500:C:T"]
        assert len(set(ids)) == 2

    def test_af_paired_with_its_own_allele(self):
        v = _make_variant(alt=["T", "G"], info={"AF": (0.2, 0.8), "DP": 20})
        recs = self._records(v)
        assert [r.allele_frequency for r in recs] == [0.2, 0.8]

    def test_variant_type_per_allele(self):
        """ALT-2 is an insertion even though ALT-1 is an SNV."""
        v = _make_variant(ref="A", alt=["T", "ATCG"], info={"DP": 20})
        assert [r.variant_type for r in self._records(v)] == ["SNV", "INS"]

    def test_ac_narrowed_to_the_allele(self):
        v = _make_variant(alt=["T", "G"], info={"AC": (7, 3), "AN": 100, "DP": 20})
        info_anns = [
            [a["additional_annotations"] for a in r.annotations
             if a["additional_annotations"].get("source") == "INFO"][0]
            for r in self._records(v)
        ]
        assert [a["ac"] for a in info_anns] == [7, 3]
        assert [a["an"] for a in info_anns] == [100, 100]  # AN is site-level

    def test_missing_af_for_second_alt_is_none(self):
        v = _make_variant(alt=["T", "G"], info={"AF": (0.2,), "DP": 20})
        assert [r.allele_frequency for r in self._records(v)] == [0.2, None]

    def test_single_alt_still_yields_one_record(self):
        v = _make_variant(alt=["T"], info={"DP": 20})
        assert len(self._records(v)) == 1

    def test_no_alt_yields_one_unknown_record(self):
        v = _make_variant(info={"DP": 20})
        v.ALT = []  # a site with no ALT allele (e.g. a "." record)
        recs = self._records(v)
        assert len(recs) == 1
        assert recs[0].variant_type == "unknown"

    def test_stats_count_emitted_records(self):
        v = _make_variant(alt=["T", "G", "C"], info={"DP": 20})
        self._records(v)
        assert self.t.stats["variants_processed"] == 3


# ===================================================================
# TestDatasetAttribution
# ===================================================================

class TestDatasetAttribution:
    """Variants must carry dataset_ids — the API filters on it per dataset."""

    def test_dataset_id_from_constructor(self):
        t = _make_transformer()
        t.dataset_id = "H3A-V6-AFR"
        rec = t._create_variant_record(_make_variant(), "GRCh38")
        assert rec.dataset_ids == ["H3A-V6-AFR"]

    def test_dataset_id_argument_wins(self):
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {}},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
            "dataset": {"id": "from-config"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            assert VCFTransformer(dataset_id="from-cli").dataset_id == "from-cli"
            assert VCFTransformer().dataset_id == "from-config"

    def test_no_dataset_id_gives_empty_list(self):
        rec = _make_transformer()._create_variant_record(_make_variant(), "GRCh38")
        assert rec.dataset_ids == []

    def test_no_dataset_id_warns_that_variants_belong_to_no_dataset(self, caplog):
        # An empty dataset_ids is a silent trap: the variants load but belong to
        # no dataset, so /datasets lists nothing and dataset-scoped queries miss them.
        with caplog.at_level(logging.WARNING):
            _make_transformer()
        warned = [r for r in caplog.records
                  if r.levelno == logging.WARNING and "--dataset-id" in r.getMessage()]
        assert warned, "expected a warning naming --dataset-id"

    def test_dataset_id_given_does_not_warn(self, caplog):
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {}},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            with caplog.at_level(logging.WARNING):
                VCFTransformer(dataset_id="MY_DATASET")
        assert not [r for r in caplog.records if "--dataset-id" in r.getMessage()]

    def test_dataset_id_from_config_does_not_warn(self, caplog):
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {}},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
            "dataset": {"id": "from-config"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            with caplog.at_level(logging.WARNING):
                VCFTransformer()
        assert not [r for r in caplog.records if "--dataset-id" in r.getMessage()]

    def test_dataset_ids_survive_serialization(self, tmp_path):
        """The field must reach the JSONL under the exact name the API queries."""
        t = _make_transformer()
        t.dataset_id = "H3A-V6-AFR"
        out = tmp_path / "out"
        v = _make_variant(pos=100, alt=["T"], info={"DP": 20})
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([v]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))
        rec = json.loads((out / "variants_batch.jsonl").read_text().strip().splitlines()[0])
        assert rec["dataset_ids"] == ["H3A-V6-AFR"]


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

    def _by_source(self, anns, source):
        return [a for a in anns
                if a.get("additional_annotations", {}).get("source") == source]

    def test_empty_info(self):
        v = _make_variant(info={})
        anns = self.t._extract_annotations(v)
        assert anns == []

    def test_vep_csq_parsed(self):
        """CSQ is read through INFO.get() — `'CSQ' in info` never matched."""
        self.t._csq_columns = ["Allele", "Consequence", "IMPACT", "SYMBOL", "Gene"]
        v = _make_variant(ref="A", alt=["T"],
                          info={"CSQ": "T|missense_variant|MODERATE|BRCA1|ENSG00000012048"})
        vep = self._by_source(self.t._extract_annotations(v), "VEP")
        assert len(vep) == 1
        assert vep[0]["gene_symbol"] == "BRCA1"
        assert vep[0]["gene_id"] == "ENSG00000012048"
        assert vep[0]["molecular_consequence"] == "missense_variant"

    def test_snpeff_ann_parsed(self):
        """ANN uses the documented SnpEff layout when the header omits it."""
        v = _make_variant(ref="A", alt=["T"], info={
            "ANN": "T|frameshift_variant|HIGH|BRCA2|ENSG00000139618|transcript|ENST1"
        })
        snpeff = self._by_source(self.t._extract_annotations(v), "SnpEff")
        assert len(snpeff) == 1
        assert snpeff[0]["gene_symbol"] == "BRCA2"
        assert snpeff[0]["molecular_consequence"] == "frameshift_variant"

    def test_basic_info_fields(self):
        v = _make_variant(info={"GENE": "BRCA1", "AF": 0.5})
        info_ann = self._by_source(self.t._extract_annotations(v), "INFO")
        assert len(info_ann) == 1
        assert info_ann[0]["gene_symbol"] == "BRCA1"
        assert info_ann[0]["additional_annotations"]["af"] == 0.5

    def test_no_info_attribute(self):
        """Variant without INFO attr returns empty list."""
        v = MagicMock(spec=[])  # no attributes at all
        anns = self.t._extract_annotations(v)
        assert anns == []

    def test_every_annotation_uses_the_model_shape(self):
        """Only VariantAnnotation fields are emitted, so the ODM can read them."""
        allowed = {"gene_id", "gene_symbol", "molecular_consequence",
                   "clinical_significance", "additional_annotations"}
        self.t._csq_columns = ["Allele", "Consequence", "SYMBOL", "Gene", "CLIN_SIG"]
        v = _make_variant(ref="A", alt=["T"], info={
            "CSQ": "T|missense_variant|BRCA1|ENSG1|pathogenic",
            "ANN": "T|stop_gained|HIGH|BRCA1|ENSG1",
            "GENE": "BRCA1", "AF": 0.1, "AN": 100,
        })
        anns = self.t._extract_annotations(v)
        assert len(anns) == 3
        for ann in anns:
            assert set(ann) <= allowed

    def test_clinical_significance_mapped(self):
        self.t._csq_columns = ["Allele", "Consequence", "SYMBOL", "CLIN_SIG"]
        v = _make_variant(ref="A", alt=["T"],
                          info={"CSQ": "T|missense_variant|BRCA1|pathogenic"})
        vep = self._by_source(self.t._extract_annotations(v), "VEP")
        assert vep[0]["clinical_significance"] == "pathogenic"

    def test_unmapped_columns_land_in_additional_annotations(self):
        self.t._csq_columns = ["Allele", "Consequence", "SYMBOL", "IMPACT", "BIOTYPE"]
        v = _make_variant(ref="A", alt=["T"],
                          info={"CSQ": "T|missense_variant|BRCA1|MODERATE|protein_coding"})
        extra = self._by_source(self.t._extract_annotations(v), "VEP")[0]["additional_annotations"]
        assert extra["impact"] == "MODERATE"
        assert extra["biotype"] == "protein_coding"


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

    def test_multiallelic_af_is_per_allele(self):
        """
        A multi-allelic site carries one AF per ALT, and each ALT is emitted as
        its own record — so the AF is indexed by the allele being described.
        """
        v = _make_variant(info={"AF": (0.1, 0.9)})
        assert self.t._extract_allele_frequency(v, 0) == pytest.approx(0.1)
        assert self.t._extract_allele_frequency(v, 1) == pytest.approx(0.9)

    def test_af_shorter_than_alt_list_returns_none(self):
        """Fewer AF entries than ALTs must yield None, never a mispaired AF."""
        v = _make_variant(alt=["T", "G"], info={"AF": (0.1,)})
        assert self.t._extract_allele_frequency(v, 1) is None

    def test_scalar_af_is_not_reused_for_second_alt(self):
        """A scalar AF describes ALT[0] only."""
        v = _make_variant(alt=["T", "G"], info={"AF": 0.4})
        assert self.t._extract_allele_frequency(v, 0) == pytest.approx(0.4)
        assert self.t._extract_allele_frequency(v, 1) is None

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
    """Verify the VEP/SnpEff parsers: header-driven columns, per-allele mapping."""

    def setup_method(self):
        self.t = _make_transformer()
        self.t._csq_columns = ["Allele", "Consequence", "IMPACT", "SYMBOL", "Gene"]

    def test_vep_string_value_is_split_on_commas(self):
        """cyvcf2 returns one comma-joined string for a Number=. field."""
        anns = self.t._parse_vep_annotations(
            "T|missense_variant|MODERATE|BRCA1|ENSG1,T|synonymous_variant|LOW|BRCA1|ENSG1",
            ref="A", alt_allele="T")
        assert [a["molecular_consequence"] for a in anns] == [
            "missense_variant", "synonymous_variant"]

    def test_vep_list_value_also_accepted(self):
        anns = self.t._parse_vep_annotations(
            ["T|missense_variant|MODERATE|BRCA1|ENSG1"], ref="A", alt_allele="T")
        assert len(anns) == 1
        assert anns[0]["gene_symbol"] == "BRCA1"

    def test_vep_without_declared_columns_emits_nothing(self):
        """No header format → no confident mapping → no fabricated gene symbol."""
        self.t._csq_columns = None
        assert self.t._parse_vep_annotations(
            "T|missense_variant|MODERATE|BRCA1|ENSG1", ref="A", alt_allele="T") == []
        assert self.t.stats["annotations_skipped"] == 1

    def test_vep_entry_with_too_many_fields_is_dropped(self):
        """More fields than the header declares means the columns are shifted."""
        assert self.t._parse_vep_annotations(
            "T|missense_variant|MODERATE|BRCA1|ENSG1|EXTRA|MORE",
            ref="A", alt_allele="T") == []
        assert self.t.stats["annotations_skipped"] == 1

    def test_vep_entry_with_no_usable_field_is_dropped(self):
        self.t._csq_columns = ["Allele", "IMPACT"]
        assert self.t._parse_vep_annotations("T|MODERATE", ref="A", alt_allele="T") == []

    def test_vep_none_yields_nothing(self):
        assert self.t._parse_vep_annotations(None, ref="A", alt_allele="T") == []

    def test_snpeff_uses_documented_default_layout(self):
        anns = self.t._parse_snpeff_annotations(
            "T|missense_variant|MODERATE|BRCA1|ENSG1|transcript|ENST1|protein_coding",
            ref="A", alt_allele="T")
        assert anns[0]["gene_symbol"] == "BRCA1"
        assert anns[0]["gene_id"] == "ENSG1"
        assert anns[0]["additional_annotations"]["annotation_impact"] == "MODERATE"

    def test_snpeff_header_layout_overrides_the_default(self):
        self.t._ann_columns = ["Allele", "Gene_Name", "Annotation"]
        anns = self.t._parse_snpeff_annotations("T|TP53|stop_gained",
                                                ref="A", alt_allele="T")
        assert anns[0]["gene_symbol"] == "TP53"
        assert anns[0]["molecular_consequence"] == "stop_gained"


# ===================================================================
# TestAnnotationAlleleAttribution
# ===================================================================

class TestAnnotationAlleleAttribution:
    """A CSQ/ANN entry must reach the record for its own ALT allele."""

    def setup_method(self):
        self.t = _make_transformer()
        self.t._csq_columns = ["Allele", "Consequence", "SYMBOL"]

    def test_allele_column_selects_the_right_alt(self):
        csq = "T|missense_variant|BRCA1,G|stop_gained|BRCA2"
        first = self.t._parse_vep_annotations(csq, ref="A", alt_allele="T",
                                              alt_index=0, n_alts=2)
        second = self.t._parse_vep_annotations(csq, ref="A", alt_allele="G",
                                               alt_index=1, n_alts=2)
        assert [a["gene_symbol"] for a in first] == ["BRCA1"]
        assert [a["gene_symbol"] for a in second] == ["BRCA2"]

    def test_allele_num_wins_over_the_allele_string(self):
        self.t._csq_columns = ["Allele", "Consequence", "SYMBOL", "ALLELE_NUM"]
        csq = "-|frameshift_variant|BRCA1|2"
        assert self.t._parse_vep_annotations(csq, ref="AT", alt_allele="A",
                                             alt_index=0, n_alts=2) == []
        matched = self.t._parse_vep_annotations(csq, ref="AT", alt_allele="A",
                                                alt_index=1, n_alts=2)
        assert [a["gene_symbol"] for a in matched] == ["BRCA1"]

    def test_vep_minimal_allele_form_matches_an_indel(self):
        """VEP writes REF=CA/ALT=C as `-`, and REF=C/ALT=CA as `A`."""
        deletion = self.t._parse_vep_annotations(
            "-|frameshift_variant|BRCA1", ref="CA", alt_allele="C",
            alt_index=0, n_alts=2)
        insertion = self.t._parse_vep_annotations(
            "A|inframe_insertion|BRCA1", ref="C", alt_allele="CA",
            alt_index=1, n_alts=2)
        assert len(deletion) == 1 and len(insertion) == 1

    def test_unattributable_entry_dropped_on_multiallelic_site(self):
        """No ALLELE_NUM and no matching allele → drop rather than misattribute."""
        assert self.t._parse_vep_annotations(
            "C|missense_variant|BRCA1", ref="A", alt_allele="T",
            alt_index=0, n_alts=2) == []
        assert self.t.stats["annotations_skipped"] == 1

    def test_biallelic_site_keeps_an_unmatched_entry(self):
        """With one ALT there is no other allele to confuse it with."""
        anns = self.t._parse_vep_annotations(
            "deletion|frameshift_variant|BRCA1", ref="A", alt_allele="T",
            alt_index=0, n_alts=1)
        assert [a["gene_symbol"] for a in anns] == ["BRCA1"]

    def test_annotations_follow_their_allele_through_parse_vcf(self):
        vcf = FakeVCF(
            [_make_variant(chrom="1", pos=100, ref="A", alt=["T", "G"],
                           info={"CSQ": "T|missense_variant|BRCA1,G|stop_gained|BRCA2"})],
            header_types={"CSQ": {"ID": "CSQ",
                                  "Description": '"Format: Allele|Consequence|SYMBOL"'}},
        )
        recs = _run_parse(self.t, None, vcf=vcf)
        symbols = [[a.get("gene_symbol") for a in r.annotations
                    if a["additional_annotations"]["source"] == "VEP"] for r in recs]
        assert symbols == [["BRCA1"], ["BRCA2"]]


# ===================================================================
# TestCsqHeaderFormat
# ===================================================================

class TestCsqHeaderFormat:
    """The CSQ column order is read from the VCF header, never assumed."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_columns_read_from_get_header_type(self):
        vcf = FakeVCF(header_types={"CSQ": {"ID": "CSQ", "Description": VEP_CSQ_DESCRIPTION}})
        cols = self.t._read_format_columns(vcf, "CSQ")
        assert cols[:5] == ["Allele", "Consequence", "IMPACT", "SYMBOL", "Gene"]

    def test_columns_read_from_raw_header_when_typed_lookup_absent(self):
        raw = (
            "##fileformat=VCFv4.2\n"
            "##INFO=<ID=CSQ,Number=.,Type=String,Description=" + VEP_CSQ_DESCRIPTION + ">\n"
            "#CHROM\tPOS\tID\tREF\tALT\n"
        )
        vcf = FakeVCF(raw_header=raw)
        assert self.t._read_format_columns(vcf, "CSQ")[3] == "SYMBOL"

    def test_snpeff_description_form_is_parsed(self):
        vcf = FakeVCF(header_types={"ANN": {"Description": SNPEFF_ANN_DESCRIPTION}})
        cols = self.t._read_format_columns(vcf, "ANN")
        assert cols[:5] == ["Allele", "Annotation", "Annotation_Impact",
                            "Gene_Name", "Gene_ID"]

    def test_missing_header_returns_none(self):
        assert self.t._read_format_columns(FakeVCF(), "CSQ") is None

    def test_description_without_a_format_clause_returns_none(self):
        vcf = FakeVCF(header_types={"CSQ": {"Description": '"just a comment"'}})
        assert self.t._read_format_columns(vcf, "CSQ") is None

    def test_a_reordered_header_remaps_the_columns(self):
        """The same CSQ string means different things under a different header."""
        reordered = '"Format: Allele|SYMBOL|Consequence"'
        vcf = FakeVCF(
            [_make_variant(ref="A", alt=["T"], info={"CSQ": "T|BRCA1|missense_variant"})],
            header_types={"CSQ": {"Description": reordered}},
        )
        rec = _run_parse(self.t, None, vcf=vcf)[0]
        vep = [a for a in rec.annotations
               if a["additional_annotations"]["source"] == "VEP"][0]
        assert vep["gene_symbol"] == "BRCA1"
        assert vep["molecular_consequence"] == "missense_variant"

    def test_no_csq_header_leaves_annotations_unparsed(self):
        vcf = FakeVCF([_make_variant(ref="A", alt=["T"],
                                     info={"CSQ": "T|missense_variant|BRCA1"})])
        rec = _run_parse(self.t, None, vcf=vcf)[0]
        assert rec.annotations == []
        assert self.t.stats["annotations_skipped"] == 1


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

    # -- unknown optional fields are omitted, never written as null or NaN --
    #
    # The individual schema types sex/ethnicity/geographic_origin as strings and
    # age as an integer, none nullable. A run without --metadata used to write
    # all four as null, so `validate_json.py --schema-type individual` (and the
    # pipeline script's own validation step) failed for every such run.

    @staticmethod
    def _run_individuals(transformer, out, samples, metadata_file=None):
        mock_vcf = MagicMock()
        mock_vcf.samples = samples
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            transformer.transform_vcf_to_beacon(
                "fake.vcf", str(out), metadata_file=metadata_file)
        return out / "individuals.json"

    @staticmethod
    def _strict_json(path):
        """Parse like a strict consumer: NaN and Infinity are not valid JSON."""
        def refuse(name):
            raise ValueError("non-standard JSON constant %r in %s" % (name, path))
        return json.loads(path.read_text(), parse_constant=refuse)

    def test_no_metadata_omits_unknown_fields(self, tmp_path):
        path = self._run_individuals(self.t, tmp_path / "out", ["S1", "S2"])
        data = self._strict_json(path)
        for rec in data:
            assert None not in rec.values(), rec
            for field in ("sex", "ethnicity", "geographic_origin", "age"):
                assert field not in rec, (field, rec)
        assert [r["id"] for r in data] == ["S1", "S2"]

    def test_unknown_fields_do_not_drop_the_known_ones(self, tmp_path):
        data = self._strict_json(
            self._run_individuals(self.t, tmp_path / "out", ["S1"]))
        rec = data[0]
        assert rec["diseases"] == {} and rec["phenotypic_features"] == {}
        assert rec["created"] and rec["updated"]

    def test_blank_metadata_cells_are_omitted_not_nan(self, tmp_path):
        meta = tmp_path / "meta.csv"
        meta.write_text(
            "sample_id,sex,ethnicity,geographic_origin,age\n"
            "S1,MALE,Yoruba,Nigeria,30\n"
            "S2,,Zulu,South Africa,\n")
        path = self._run_individuals(
            self.t, tmp_path / "out", ["S1", "S2", "S3"], str(meta))
        by_id = {r["id"]: r for r in self._strict_json(path)}
        assert by_id["S2"]["ethnicity"] == "Zulu"
        assert "sex" not in by_id["S2"] and "age" not in by_id["S2"]
        # S3 has no metadata row at all.
        assert not {"sex", "ethnicity", "geographic_origin", "age"} & set(by_id["S3"])

    def test_metadata_values_are_kept_and_age_is_an_integer(self, tmp_path):
        # A blank age elsewhere in the column makes pandas read the whole column
        # as float, which would turn 30 into 30.0.
        meta = tmp_path / "meta.csv"
        meta.write_text(
            "sample_id,sex,ethnicity,geographic_origin,age\n"
            "S1,MALE,Yoruba,Nigeria,30\n"
            "S2,FEMALE,Zulu,South Africa,\n")
        path = self._run_individuals(
            self.t, tmp_path / "out", ["S1", "S2"], str(meta))
        s1 = {r["id"]: r for r in self._strict_json(path)}["S1"]
        assert s1["sex"] == "MALE" and s1["ethnicity"] == "Yoruba"
        assert s1["age"] == 30 and isinstance(s1["age"], int)
        assert not isinstance(s1["age"], bool)

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


# ===================================================================
# TestSymbolicAndStructuralAlleles
# ===================================================================

class TestSymbolicAndStructuralAlleles:
    """`<DEL>` is 5 characters — it must never be typed by string length."""

    def setup_method(self):
        self.t = _make_transformer()

    @pytest.mark.parametrize("alt,expected", [
        ("<DEL>", "DEL"),
        ("<DUP>", "DUP"),
        ("<INS>", "INS"),
        ("<INV>", "INV"),
        ("<CNV>", "CNV"),
        ("<DUP:TANDEM>", "DUP"),
        ("<CNV:TR>", "CNV"),
        ("<INS:ME:ALU>", "INS"),
    ])
    def test_symbolic_types(self, alt, expected):
        assert self.t._determine_variant_type("A", [alt]) == expected

    def test_unknown_symbolic_type_is_generic_sv(self):
        assert self.t._determine_variant_type("A", ["<FOO>"]) == "SV"

    @pytest.mark.parametrize("alt", ["A[chr2:321682[", "]chr2:321681]T", "A]2:100]"])
    def test_breakend_notation(self, alt):
        assert self.t._determine_variant_type("A", [alt]) == "BND"

    def test_spanning_deletion_allele_is_unknown(self):
        assert self.t._determine_variant_type("A", ["*"]) == "unknown"

    def test_empty_ref_is_unknown(self):
        assert self.t._determine_variant_type("", ["T"]) == "unknown"

    def test_symbolic_deletion_span_comes_from_end(self):
        """POS 1000, END 11000 → a 10 kb span, not 1 bp."""
        v = _make_variant(pos=1000, ref="N", alt=["<DEL>"], info={"END": 11000})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert (rec.start, rec.end) == (999, 11000)
        assert rec.variant_type == "DEL"

    def test_end_is_used_for_sequence_alleles_too(self):
        v = _make_variant(pos=100, ref="A", alt=["T"], info={"END": 250})
        assert self.t._create_variant_record(v, "GRCh38").end == 250

    def test_svlen_used_when_end_absent(self):
        v = _make_variant(pos=1000, ref="N", alt=["<DEL>"], info={"SVLEN": -500})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.end == 999 + 500

    def test_svlen_is_per_allele(self):
        v = _make_variant(pos=1000, ref="N", alt=["<DEL>", "<DUP>"],
                          info={"SVLEN": (-500, 2000)})
        assert self.t._create_variant_record(v, "GRCh38", 0).end == 999 + 500
        assert self.t._create_variant_record(v, "GRCh38", 1).end == 999 + 2000

    def test_symbolic_insertion_does_not_consume_reference(self):
        v = _make_variant(pos=1000, ref="N", alt=["<INS>"], info={"SVLEN": 300})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.end == 1000  # start + len(REF)

    def test_symbolic_without_span_is_skipped(self):
        v = _make_variant(pos=1000, ref="N", alt=["<DEL>"], info={})
        assert self.t._create_variant_record(v, "GRCh38") is None
        assert self.t.stats["skipped_reasons"]["symbolic_allele_without_span"] == 1

    def test_spanning_deletion_allele_is_skipped(self):
        v = _make_variant(pos=100, ref="A", alt=["*"], info={})
        assert self.t._create_variant_record(v, "GRCh38") is None
        assert self.t.stats["skipped_reasons"]["spanning_deletion_allele"] == 1

    def test_skipped_alleles_do_not_reach_the_output(self):
        v = _make_variant(pos=100, ref="A", alt=["T", "*"], info={})
        recs = _run_parse(self.t, [v])
        assert [r.alternate_bases for r in recs] == ["T"]
        assert self.t.stats["variants_processed"] == 1
        assert self.t.stats["variants_skipped"] == 1

    def test_bogus_end_before_start_is_ignored(self):
        v = _make_variant(pos=1000, ref="ATG", alt=["A"], info={"END": 5})
        assert self.t._create_variant_record(v, "GRCh38").end == 999 + 3

    def test_non_integer_end_is_ignored(self):
        v = _make_variant(pos=1000, ref="ATG", alt=["A"], info={"END": "not-a-number"})
        assert self.t._create_variant_record(v, "GRCh38").end == 999 + 3

    def test_breakend_record_is_kept_with_a_single_base_span(self):
        v = _make_variant(pos=100, ref="A", alt=["A[2:321682["], info={})
        rec = self.t._create_variant_record(v, "GRCh38")
        assert rec.variant_type == "BND"
        assert (rec.start, rec.end) == (99, 100)


# ===================================================================
# TestChromosomeNormalization
# ===================================================================

class TestChromosomeNormalization:
    """Contigs are stored bare, so the API need not `$in` both spellings."""

    def setup_method(self):
        self.t = _make_transformer()

    @pytest.mark.parametrize("raw,expected", [
        ("chr1", "1"),
        ("1", "1"),
        ("CHR7", "7"),
        ("chr22", "22"),
        ("chrX", "X"),
        ("x", "X"),
        ("chrY", "Y"),
        ("chrM", "MT"),
        ("M", "MT"),
        ("MT", "MT"),
        ("chrMT", "MT"),
        (" chr1 ", "1"),
        (1, "1"),
        ("01", "1"),
    ])
    def test_normalized_forms(self, raw, expected):
        assert self.t._normalize_chromosome(raw) == expected

    @pytest.mark.parametrize("raw", [
        "GL000220.1",
        "chrUn_KI270302v1",
        "chr1_KI270706v1_random",
        "HLA-A*01:01:01:01",
        "chr23",
    ])
    def test_unrecognised_contigs_are_left_intact(self, raw):
        assert self.t._normalize_chromosome(raw) == raw

    def test_none_becomes_empty_string(self):
        assert self.t._normalize_chromosome(None) == ""

    def test_record_stores_the_bare_name(self):
        rec = self.t._create_variant_record(
            _make_variant(chrom="chr1", pos=100), "GRCh38")
        assert rec.reference_name == "1"

    def test_variant_id_uses_the_bare_name(self):
        """Both spellings of a contig must produce the same natural key."""
        prefixed = self.t._create_variant_record(
            _make_variant(chrom="chr2", pos=500, ref="C", alt=["G"]), "GRCh38")
        bare = self.t._create_variant_record(
            _make_variant(chrom="2", pos=500, ref="C", alt=["G"]), "GRCh38")
        assert prefixed.id == bare.id == "2:500:C:G"

    def test_normalization_survives_the_pipeline(self, tmp_path):
        out = tmp_path / "out"
        v = _make_variant(chrom="chrX", pos=100, ref="A", alt=["T"], info={"DP": 20})
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=FakeVCF([v])):
            self.t.transform_vcf_to_beacon("fake.vcf", str(out))
        rec = json.loads((out / "variants_batch.jsonl").read_text().strip().splitlines()[0])
        assert rec["reference_name"] == "X"


# ===================================================================
# TestQualityFilterInfoAccess
# ===================================================================

class TestQualityFilterInfoAccess:
    """DP must be read through INFO.get() — `'DP' in INFO` is always False."""

    def setup_method(self):
        self.t = _make_transformer()

    def test_low_depth_is_filtered_through_the_real_info_api(self):
        v = _make_variant(qual=30, info={"DP": 3})
        assert self.t._passes_quality_filters(v) is False
        assert _run_parse(self.t, [v]) == []
        assert self.t.stats["variants_filtered"] == 1

    def test_string_depth_is_coerced(self):
        assert self.t._passes_quality_filters(_make_variant(qual=30, info={"DP": "3"})) is False

    def test_unparseable_depth_does_not_filter(self):
        assert self.t._passes_quality_filters(_make_variant(qual=30, info={"DP": "n/a"})) is True


# ===================================================================
# TestCarrierCheck
# ===================================================================

def _carrier_transformer(**kwargs) -> VCFTransformer:
    """A transformer whose carrier-check options come from the constructor."""
    cfg = {
        "vcf": {"default_assembly": "GRCh38", "quality_filters": {}},
        "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
    }
    with patch.object(VCFTransformer, "_load_config", return_value=cfg):
        return VCFTransformer(dataset_id="D", **kwargs)


def _sites(n_zero, n_carried, genotypes_carried=None, genotypes_zero=None):
    """``n_zero`` records no sample carries, then ``n_carried`` that some sample does."""
    ref = genotypes_zero or [[0, 0, False], [0, 0, False]]
    alt = genotypes_carried or [[0, 1, False], [0, 0, False]]
    out = []
    for i in range(n_zero):
        out.append(_make_variant(pos=1000 + i, info={"AC": 0, "AN": 4}, genotypes=ref))
    for j in range(n_carried):
        out.append(_make_variant(pos=5000 + j, info={"AC": 1, "AN": 4}, genotypes=alt))
    return out


def _warnings(caplog, needle):
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING and needle in r.getMessage()]


class TestCarrierCheckInfo:
    """A record is only honest if some sample carries its alternate allele."""

    def test_no_warning_when_every_record_has_a_carrier(self, caplog):
        t = _carrier_transformer(genotype_check_every=0)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(0, 50))
        assert not _warnings(caplog, "AC = 0")
        assert t.warnings == []
        assert t.stats["ac_checked"] == 50 and t.stats["ac_zero"] == 0

    def test_warns_when_the_share_of_ac_zero_exceeds_the_default_threshold(self, caplog):
        t = _carrier_transformer(genotype_check_every=0)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(2, 98))              # 2% > 1%
        assert len(_warnings(caplog, "AC = 0")) == 1
        assert len(t.warnings) == 1

    def test_the_threshold_is_strictly_greater_than(self, caplog):
        t = _carrier_transformer(genotype_check_every=0)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(1, 99))              # exactly 1%
        assert not _warnings(caplog, "AC = 0")

    def test_the_threshold_is_configurable(self, caplog):
        t = _carrier_transformer(warn_ac_zero_fraction=0.5, genotype_check_every=0)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(30, 70))             # 30% < 50%
        assert not _warnings(caplog, "AC = 0")

    def test_the_threshold_can_come_from_the_config_file(self, caplog):
        cfg = {
            "vcf": {"default_assembly": "GRCh38", "quality_filters": {},
                    "warn_ac_zero_fraction": 0.5, "genotype_check_every": 0},
            "processing": {"batch_size": 100, "show_progress": False, "log_level": "WARNING"},
        }
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            t = VCFTransformer(dataset_id="D")
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(30, 70))
        assert not _warnings(caplog, "AC = 0")
        assert t.warn_ac_zero_fraction == 0.5

    def test_zero_counts_in_every_numeric_form(self):
        np = pytest.importorskip("numpy")
        t = _carrier_transformer(genotype_check_every=0)
        variants = [_make_variant(pos=100 + i, info={"AC": value})
                    for i, value in enumerate([0, 0.0, np.int64(0), np.float32(0.0)])]
        _run_parse(t, variants)
        assert t.stats["ac_zero"] == 4

    def test_a_multiallelic_site_counts_only_the_allele_with_no_carrier(self):
        t = _carrier_transformer(genotype_check_every=0)
        _run_parse(t, [_make_variant(alt=["A", "C"], info={"AC": (3, 0)})])
        assert t.stats["ac_checked"] == 2
        assert t.stats["ac_zero"] == 1

    def test_a_record_without_ac_is_missing_not_zero(self):
        t = _carrier_transformer(genotype_check_every=0)
        _run_parse(t, [_make_variant(info={"DP": 20})])
        assert t.stats["ac_missing"] == 1
        assert t.stats["ac_checked"] == 0 and t.stats["ac_zero"] == 0

    def test_a_non_numeric_ac_is_missing_not_zero(self):
        t = _carrier_transformer(genotype_check_every=0)
        _run_parse(t, [_make_variant(info={"AC": "n/a"})])
        assert t.stats["ac_missing"] == 1 and t.stats["ac_zero"] == 0

    def test_a_skipped_spanning_deletion_is_not_in_the_denominator(self):
        t = _carrier_transformer(genotype_check_every=0)
        _run_parse(t, [_make_variant(alt=["*", "T"], info={"AC": (0, 2)})])
        assert t.stats["ac_checked"] == 1 and t.stats["ac_zero"] == 0

    def test_a_record_dropped_by_the_quality_filter_is_not_counted(self):
        t = _make_transformer()
        _run_parse(t, [_make_variant(qual=5, info={"AC": 0})])
        assert t.stats["ac_checked"] == 0

    def test_zero_records_neither_crash_nor_warn(self, caplog):
        t = _carrier_transformer()
        with caplog.at_level(logging.WARNING):
            assert _run_parse(t, []) == []
        assert t.warnings == []

    def test_no_ac_anywhere_and_no_genotypes_warns_the_check_could_not_run(self, caplog):
        t = _carrier_transformer()
        sites = [_make_variant(pos=100 + i, info={"DP": 20}) for i in range(5)]
        for site in sites:
            site.genotypes = []   # _make_variant treats [] as "use the default"
        with caplog.at_level(logging.WARNING):
            _run_parse(t, sites)
        assert len(_warnings(caplog, "could not be checked")) == 1

    def test_the_warning_names_the_cause_and_the_fix(self, caplog):
        t = _carrier_transformer(genotype_check_every=0)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(10, 90))
        message = _warnings(caplog, "AC = 0")[0]
        assert "10 of 100" in message and "10.0%" in message
        assert "cut to some samples" in message
        assert "bcftools view" in message and "-c1" in message
        assert "Cutting a dataset from some of the samples" in message

    def test_warning_does_not_change_what_is_emitted(self):
        with_check = _run_parse(_carrier_transformer(), _sites(10, 90))
        without = _run_parse(_carrier_transformer(genotype_check_every=0,
                                                   warn_ac_zero_fraction=1.0),
                             _sites(10, 90))
        assert [r.id for r in with_check] == [r.id for r in without]
        assert len(with_check) == 100


class TestCarrierCheckGenotypes:
    """INFO can be stale or absent, so a sample of records is checked against genotypes."""

    def test_samples_the_first_and_every_nth_record(self):
        t = _carrier_transformer(genotype_check_every=10)
        _run_parse(t, _sites(0, 25))
        assert t.stats["genotype_checked"] == 3        # records 0, 10, 20

    def test_every_zero_turns_it_off(self):
        t = _carrier_transformer(genotype_check_every=0)
        _run_parse(t, _sites(0, 25))
        assert t.stats["genotype_checked"] == 0

    def test_genotypes_are_not_read_when_the_check_is_off(self):
        t = _carrier_transformer(genotype_check_every=0)
        v = _make_variant(info={"AC": 1})
        touched = []
        type(v).genotypes = PropertyMock(side_effect=lambda: touched.append(1) or [])
        _run_parse(t, [v])
        assert touched == []

    def test_stale_info_is_caught_by_the_genotypes(self, caplog):
        # INFO says 5 carriers, the genotypes say none: the counts describe
        # another cohort, or were not recomputed after the samples were cut.
        t = _carrier_transformer(genotype_check_every=1)
        stale = [_make_variant(pos=100 + i, info={"AC": 5, "AN": 4},
                               genotypes=[[0, 0, False], [0, 0, False]]) for i in range(20)]
        with caplog.at_level(logging.WARNING):
            _run_parse(t, stale)
        assert t.stats["info_genotype_mismatch"] == 20
        assert len(_warnings(caplog, "disagrees with the genotypes")) == 1
        assert "not recomputed" in _warnings(caplog, "disagrees")[0]

    def test_genotypes_catch_what_missing_info_hides(self, caplog):
        t = _carrier_transformer(genotype_check_every=1)
        sites = [_make_variant(pos=100 + i, info={"DP": 20},
                               genotypes=[[0, 0, False], [0, 0, False]]) for i in range(20)]
        with caplog.at_level(logging.WARNING):
            _run_parse(t, sites)
        assert t.stats["genotype_ac_zero"] == 20
        assert len(_warnings(caplog, "no carrier in the genotypes")) == 1

    def test_agreeing_info_and_genotypes_do_not_warn(self, caplog):
        t = _carrier_transformer(genotype_check_every=1)
        with caplog.at_level(logging.WARNING):
            _run_parse(t, _sites(0, 20))
        assert t.warnings == []
        assert t.stats["info_genotype_mismatch"] == 0
        assert t.stats["info_genotype_compared"] == 20

    def test_multiallelic_genotypes_are_counted_by_allele_index(self):
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(alt=["A", "C"], info={"AC": (3, 1)},
                          genotypes=[[1, 2, False], [1, 1, False], [0, 0, False]])
        _run_parse(t, [v])
        assert t.stats["genotype_checked"] == 2
        assert t.stats["genotype_ac_zero"] == 0
        assert t.stats["info_genotype_mismatch"] == 0

    def test_haploid_and_missing_genotypes_are_handled(self):
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(info={"AC": 2},
                          genotypes=[[1, False], [-1, -1, False], [0, 1, False]])
        _run_parse(t, [v])
        assert t.stats["info_genotype_mismatch"] == 0 and t.stats["genotype_ac_zero"] == 0

    def test_a_sites_only_vcf_skips_the_check_without_crashing(self):
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(info={"AC": 1})
        v.genotypes = []          # _make_variant treats [] as "use the default"
        _run_parse(t, [v])
        assert t.stats["genotype_checked"] == 0
        assert t.stats["genotype_check_unavailable"] == 1

    def test_unreadable_genotypes_skip_the_check_without_crashing(self):
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(info={"AC": 1})
        v.genotypes = None
        _run_parse(t, [v])
        assert t.stats["genotype_check_unavailable"] == 1

    def test_a_mismatch_is_not_counted_when_info_is_missing(self):
        t = _carrier_transformer(genotype_check_every=1)
        _run_parse(t, [_make_variant(info={"DP": 20})])
        assert t.stats["info_genotype_compared"] == 0
        assert t.stats["info_genotype_mismatch"] == 0


    def test_the_phased_flag_is_not_an_allele(self):
        # cyvcf2's last list entry is the phased flag; True == 1 would count it
        # as a copy of the first ALT allele at every phased reference call.
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(info={"AC": 0}, genotypes=[[0, 0, True], [0, 0, True]])
        _run_parse(t, [v])
        assert t.stats["genotype_ac_zero"] == 1
        assert t.stats["info_genotype_mismatch"] == 0

    def test_info_lower_than_the_genotypes_is_a_mismatch_too(self):
        t = _carrier_transformer(genotype_check_every=1)
        v = _make_variant(info={"AC": 1},
                          genotypes=[[1, 1, False], [0, 1, False]])      # three copies
        _run_parse(t, [v])
        assert t.stats["info_genotype_mismatch"] == 1


class TestCarrierCheckReporting:
    """The counters and warnings must reach the files and the screen people read."""

    def _transform(self, tmp_path, variants, **kwargs):
        t = _carrier_transformer(**kwargs)
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=FakeVCF(variants)):
            summary = t.transform_vcf_to_beacon("fake.vcf", str(out))
        return summary, out

    def test_counters_and_warnings_land_in_the_summary_file(self, tmp_path):
        summary, out = self._transform(tmp_path, _sites(10, 90), genotype_check_every=1)
        on_disk = json.loads((out / "transformation_summary.json").read_text())
        assert on_disk["statistics"]["ac_zero"] == 10
        assert on_disk["statistics"]["ac_checked"] == 100
        assert len(on_disk["warnings"]) == len(summary["warnings"]) >= 1
        assert any("AC = 0" in w for w in on_disk["warnings"])

    def test_a_clean_run_has_an_empty_warnings_list(self, tmp_path):
        _, out = self._transform(tmp_path, _sites(0, 50), genotype_check_every=1)
        assert json.loads((out / "transformation_summary.json").read_text())["warnings"] == []

    def test_main_prints_the_warnings_after_the_statistics(self, capsys):
        from vcf_transform import vcf_to_beacon
        summary = {"statistics": {}, "files_created": [], "warnings": ["W-ONE", "W-TWO"]}
        with patch.object(vcf_to_beacon, "VCFTransformer") as klass:
            klass.return_value.transform_vcf_to_beacon.return_value = summary
            vcf_to_beacon.main(["in.vcf", "-o", "out"])
        printed = capsys.readouterr().out
        assert "W-ONE" in printed and "W-TWO" in printed
        assert printed.index("Statistics") < printed.index("W-ONE")

    def test_main_passes_the_two_flags_to_the_transformer(self):
        from vcf_transform import vcf_to_beacon
        summary = {"statistics": {}, "files_created": [], "warnings": []}
        with patch.object(vcf_to_beacon, "VCFTransformer") as klass:
            klass.return_value.transform_vcf_to_beacon.return_value = summary
            vcf_to_beacon.main(["in.vcf", "-o", "out", "--warn-ac-zero-fraction", "0.25",
                                "--genotype-check-every", "50"])
        kwargs = klass.call_args.kwargs
        assert kwargs["warn_ac_zero_fraction"] == 0.25
        assert kwargs["genotype_check_every"] == 50

    def test_main_defaults_leave_the_choice_to_the_config(self):
        from vcf_transform import vcf_to_beacon
        summary = {"statistics": {}, "files_created": [], "warnings": []}
        with patch.object(vcf_to_beacon, "VCFTransformer") as klass:
            klass.return_value.transform_vcf_to_beacon.return_value = summary
            vcf_to_beacon.main(["in.vcf", "-o", "out"])
        kwargs = klass.call_args.kwargs
        assert kwargs["warn_ac_zero_fraction"] is None
        assert kwargs["genotype_check_every"] is None

    def test_out_of_range_options_are_refused(self):
        with pytest.raises(ValueError):
            _carrier_transformer(warn_ac_zero_fraction=1.5)
        with pytest.raises(ValueError):
            _carrier_transformer(warn_ac_zero_fraction=-0.1)
        with pytest.raises(ValueError):
            _carrier_transformer(genotype_check_every=-1)
