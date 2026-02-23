"""Test-level conftest: mock factories for VCF variants, MongoDB, ontology lookups."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock cyvcf2 objects
# ---------------------------------------------------------------------------

class MockVariant:
    """Lightweight mock for a cyvcf2 Variant record."""

    def __init__(
        self,
        chrom: str = "1",
        pos: int = 100001,
        ref: str = "A",
        alt: list = None,
        qual: float = 30.0,
        info: dict = None,
        genotypes: list = None,
        filter: str = None,
    ):
        self.CHROM = chrom
        self.POS = pos
        self.REF = ref
        self.ALT = alt or ["T"]
        self.QUAL = qual
        self.FILTER = filter
        self._info = info or {}
        self.genotypes = genotypes or [[0, 1, False]]

    @property
    def INFO(self):
        return self._info

    def format(self):
        return {}


class MockVCF:
    """Lightweight mock for cyvcf2.VCF that iterates MockVariant objects."""

    def __init__(self, variants: list = None, samples: list = None):
        self._variants = variants or []
        self.samples = samples or ["SAMPLE1"]

    def __iter__(self):
        return iter(self._variants)


@pytest.fixture()
def mock_variant_factory():
    """Factory fixture that returns a MockVariant builder."""
    def _make(**kwargs) -> MockVariant:
        return MockVariant(**kwargs)
    return _make


@pytest.fixture()
def mock_vcf_factory():
    """Factory fixture that returns a MockVCF builder."""
    def _make(variants=None, samples=None) -> MockVCF:
        return MockVCF(variants=variants, samples=samples)
    return _make


# ---------------------------------------------------------------------------
# Mock MongoDB helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_mongo_client():
    """Return a MagicMock pretending to be a pymongo.MongoClient."""
    client = MagicMock()
    client.admin.command.return_value = {"ok": 1}
    return client


@pytest.fixture()
def mock_collection():
    """Return a MagicMock pretending to be a pymongo.Collection."""
    coll = MagicMock()
    coll.insert_many.return_value = MagicMock(inserted_ids=["id1", "id2"])
    coll.insert_one.return_value = MagicMock(inserted_id="id1")
    coll.count_documents.return_value = 0
    coll.find.return_value = iter([])
    return coll


# ---------------------------------------------------------------------------
# Temp-directory helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_json_file(tmp_path):
    """Write a list of dicts to a temp JSON file and return its path."""
    def _make(data: list, filename: str = "data.json") -> Path:
        fp = tmp_path / filename
        fp.write_text(json.dumps(data, indent=2))
        return fp
    return _make


@pytest.fixture()
def tmp_jsonl_file(tmp_path):
    """Write records as JSONL and return the path."""
    def _make(data: list, filename: str = "data.jsonl") -> Path:
        fp = tmp_path / filename
        fp.write_text("\n".join(json.dumps(r) for r in data) + "\n")
        return fp
    return _make
