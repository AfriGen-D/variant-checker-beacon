"""Root conftest: fixture paths, config overrides, shared session-scoped fixtures."""
import os
import sys
from pathlib import Path

import pytest

# Ensure package root is on sys.path for imports
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES_DIR = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def vcf_fixtures_dir():
    return FIXTURES_DIR / "vcf"


@pytest.fixture(scope="session")
def phenotype_fixtures_dir():
    return FIXTURES_DIR / "phenotype"


@pytest.fixture(scope="session")
def json_fixtures_dir():
    return FIXTURES_DIR / "json"


@pytest.fixture()
def default_config():
    """Minimal config dict used by all transformers when no YAML file exists."""
    return {
        "vcf": {
            "default_assembly": "GRCh38",
            "quality_filters": {"min_qual": 20, "min_depth": 10},
        },
        "phenotypes": {
            "default_ontology": "HPO",
            "supported_formats": ["csv", "tsv", "xlsx", "json"],
        },
        "validation": {
            "strict_mode": False,
            "required_fields_check": True,
            "type_validation": True,
            "range_validation": True,
        },
        "mongodb": {
            "host": "localhost",
            "port": 27017,
            "database": "beacon_test_db",
            "connection_timeout": 5,
        },
        "processing": {
            "batch_size": 100,
            "show_progress": False,
            "log_level": "WARNING",
        },
        "output": {
            "pretty_json": True,
            "include_metadata": True,
        },
    }
