"""Tests for the dataset metadata file (dataset.yaml)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data_import.dataset_file import DatasetFileError, load_dataset_file, parse_dataset_text  # noqa: E402

VALID = """
dataset:
  id: 1000G_CHR22_SUBSET
  name: 1000 Genomes chr22 test subset
  description: Nine samples, one region.
  assembly: GRCh38
  contact:
    name: A Person
    email: a.person@example.org
"""


class TestValidFile:
    def test_all_fields_are_returned(self):
        meta = parse_dataset_text(VALID)
        assert meta["id"] == "1000G_CHR22_SUBSET"
        assert meta["name"] == "1000 Genomes chr22 test subset"
        assert meta["description"] == "Nine samples, one region."
        assert meta["assembly"] == "GRCh38"
        assert meta["contact"] == {"name": "A Person", "email": "a.person@example.org"}

    def test_only_id_and_name_are_required(self):
        meta = parse_dataset_text("dataset:\n  id: MY_DATA\n  name: My data\n")
        assert meta["id"] == "MY_DATA"
        assert meta["description"] is None
        assert meta["assembly"] is None
        assert meta["contact"] == {}

    def test_surrounding_whitespace_is_trimmed(self):
        meta = parse_dataset_text("dataset:\n  id: '  MY_DATA '\n  name: ' My data '\n")
        assert (meta["id"], meta["name"]) == ("MY_DATA", "My data")

    def test_loads_from_a_path(self, tmp_path):
        f = tmp_path / "dataset.yaml"
        f.write_text(VALID)
        assert load_dataset_file(str(f))["id"] == "1000G_CHR22_SUBSET"


class TestRefusals:
    """A wrong file must stop the run, never quietly become a different dataset."""

    @pytest.mark.parametrize("text", ["", "   \n", "# only a comment\n"])
    def test_empty_file(self, text):
        with pytest.raises(DatasetFileError, match="empty"):
            parse_dataset_text(text)

    def test_not_a_mapping(self):
        with pytest.raises(DatasetFileError, match="mapping"):
            parse_dataset_text("- a\n- b\n")

    def test_missing_dataset_section(self):
        with pytest.raises(DatasetFileError, match="dataset"):
            parse_dataset_text("id: MY_DATA\nname: x\n")

    def test_missing_id(self):
        with pytest.raises(DatasetFileError, match="id"):
            parse_dataset_text("dataset:\n  name: My data\n")

    def test_missing_name(self):
        with pytest.raises(DatasetFileError, match="name"):
            parse_dataset_text("dataset:\n  id: MY_DATA\n")

    @pytest.mark.parametrize("bad", ["has space", "semi;colon", "slash/id", "", "a" * 65])
    def test_invalid_id(self, bad):
        with pytest.raises(DatasetFileError, match="id"):
            parse_dataset_text(f"dataset:\n  id: {bad!r}\n  name: x\n")

    def test_id_must_be_text_not_a_number(self):
        # YAML reads `id: 1234` as an integer; an id is a name.
        with pytest.raises(DatasetFileError, match="id"):
            parse_dataset_text("dataset:\n  id: 1234\n  name: x\n")

    def test_unknown_key_is_refused_so_a_typo_is_not_ignored(self):
        with pytest.raises(DatasetFileError, match="discription"):
            parse_dataset_text("dataset:\n  id: A\n  name: x\n  discription: typo\n")

    def test_contact_must_be_a_mapping(self):
        with pytest.raises(DatasetFileError, match="contact"):
            parse_dataset_text("dataset:\n  id: A\n  name: x\n  contact: someone\n")

    def test_invalid_yaml(self):
        with pytest.raises(DatasetFileError, match="YAML"):
            parse_dataset_text("dataset: [unclosed\n")

    def test_missing_file(self, tmp_path):
        with pytest.raises(DatasetFileError, match="not found"):
            load_dataset_file(str(tmp_path / "nope.yaml"))
