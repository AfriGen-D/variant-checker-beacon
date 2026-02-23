"""Integration tests for VCF → Beacon pipeline using mocked cyvcf2."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Patch heavy imports
for mod in ("cyvcf2", "pysam", "biopython", "Bio", "Bio.SeqIO"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from vcf_transform.vcf_to_beacon import VCFTransformer


def _make_transformer():
    cfg = {
        "vcf": {"default_assembly": "GRCh38", "quality_filters": {"min_qual": 20, "min_depth": 10}},
        "processing": {"batch_size": 5, "show_progress": False, "log_level": "WARNING"},
    }
    with patch.object(VCFTransformer, "_load_config", return_value=cfg):
        return VCFTransformer()


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
class TestVcfEndToEnd:
    """Run transform_vcf_to_beacon with mocked cyvcf2 and verify output files."""

    def test_full_pipeline_multi_variant(self, tmp_path):
        t = _make_transformer()
        variants = [
            _mock_variant("1", 100001, "A", ["T"]),
            _mock_variant("1", 200001, "ATG", ["A"]),
            _mock_variant("2", 300001, "A", ["ATCG"]),
        ]
        mock_vcf = MagicMock()
        mock_vcf.samples = ["SAMPLE1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter(variants))
        out = tmp_path / "pipeline_out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            summary = t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert summary["statistics"]["variants_processed"] == 3
        assert (out / "variants_batch.jsonl").exists()
        assert (out / "individuals.json").exists()

    def test_coordinates_correct(self, tmp_path):
        t = _make_transformer()
        v = _mock_variant("1", 100001, "A", ["T"])
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([v]))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))
        lines = (out / "variants_batch.jsonl").read_text().strip().splitlines()
        rec = json.loads(lines[0])
        assert rec["start"] == 100000
        assert rec["end"] == 100001

    def test_low_qual_filtered(self, tmp_path):
        t = _make_transformer()
        variants = [
            _mock_variant("1", 100, "A", ["T"], qual=5),
            _mock_variant("1", 200, "C", ["G"], qual=50, info={"DP": 30}),
        ]
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter(variants))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            summary = t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert summary["statistics"]["variants_filtered"] >= 1

    def test_multiple_samples(self, tmp_path):
        t = _make_transformer()
        v = _mock_variant("1", 100, "A", ["T"], gt=[[0, 1, False], [1, 1, False], [-1, -1, False]])
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1", "S2", "S3"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([v]))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))
        individuals = json.loads((out / "individuals.json").read_text())
        assert len(individuals) == 3

    def test_batch_write(self, tmp_path):
        """With batch_size=5, 10 variants should still all appear in output."""
        cfg = {"processing": {"batch_size": 5, "show_progress": False, "log_level": "WARNING"},
               "vcf": {"default_assembly": "GRCh38", "quality_filters": {"min_qual": 0, "min_depth": 0}}}
        with patch.object(VCFTransformer, "_load_config", return_value=cfg):
            t = VCFTransformer()
        variants = [_mock_variant("1", i, "A", ["T"], qual=50, info={"DP": 30}) for i in range(10, 20)]
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter(variants))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))
        lines = (out / "variants_batch.jsonl").read_text().strip().splitlines()
        assert len(lines) == 10

    def test_variant_types_in_output(self, tmp_path):
        t = _make_transformer()
        variants = [
            _mock_variant("1", 100, "A", ["T"]),       # SNV
            _mock_variant("1", 200, "ATG", ["A"]),      # DEL
            _mock_variant("1", 300, "A", ["ATCG"]),     # INS
            _mock_variant("1", 400, "AT", ["GC"]),      # COMPLEX
        ]
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter(variants))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out))
        lines = (out / "variants_batch.jsonl").read_text().strip().splitlines()
        types = {json.loads(l)["variant_type"] for l in lines}
        assert types == {"SNV", "DEL", "INS", "COMPLEX"}

    def test_summary_contains_files_created(self, tmp_path):
        t = _make_transformer()
        mock_vcf = MagicMock()
        mock_vcf.samples = ["S1"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        out = tmp_path / "out"
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            summary = t.transform_vcf_to_beacon("fake.vcf", str(out))
        assert "variants_batch.jsonl" in summary["files_created"]
        assert "individuals.json" in summary["files_created"]

    def test_metadata_enriches_individuals(self, tmp_path, vcf_fixtures_dir):
        t = _make_transformer()
        mock_vcf = MagicMock()
        mock_vcf.samples = ["SAMPLE1", "SAMPLE2"]
        mock_vcf.__iter__ = MagicMock(return_value=iter([]))
        out = tmp_path / "out"
        metadata_file = str(vcf_fixtures_dir / "sample_metadata.csv")
        with patch("vcf_transform.vcf_to_beacon.cyvcf2.VCF", return_value=mock_vcf):
            t.transform_vcf_to_beacon("fake.vcf", str(out), metadata_file=metadata_file)
        individuals = json.loads((out / "individuals.json").read_text())
        sample1 = next((i for i in individuals if i["id"] == "SAMPLE1"), None)
        assert sample1 is not None
        assert sample1.get("sex") == "MALE"
