"""
Read and validate a dataset metadata file (``dataset.yaml``).

The file says what a loaded dataset is called, so that name is written once and
reused everywhere: the id goes into every variant's ``dataset_ids``, and the rest
becomes the record the ``/datasets`` endpoint lists. Example::

    dataset:
      id: 1000G_CHR22_SUBSET            # required; letters, digits, _ . -
      name: 1000 Genomes chr22 test subset   # required
      description: Nine samples, one region.
      assembly: GRCh38
      contact:
        name: A Person
        email: a.person@example.org

Validation is strict on purpose. A misspelt key, an id that YAML read as a
number, or an empty file would otherwise load data under a wrong or missing
dataset without any error, so each of those stops the run.

Run as a script to print one field, which is how the shell pipeline reads the id::

    python dataset_file.py dataset.yaml --get id
"""
import argparse
import re
import sys
from typing import Any, Dict, Optional

import yaml

_ALLOWED_KEYS = ("id", "name", "description", "assembly", "contact")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class DatasetFileError(ValueError):
    """The dataset file is missing, unreadable or invalid."""


def _optional_text(section: Dict[str, Any], key: str) -> Optional[str]:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DatasetFileError(f"dataset.{key} must be text, got {type(value).__name__}")
    return value.strip() or None


def parse_dataset_text(text: str) -> Dict[str, Any]:
    """Validate the YAML in ``text`` and return the dataset fields."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise DatasetFileError(f"not valid YAML: {e}") from e

    if document is None:
        raise DatasetFileError("the dataset file is empty")
    if not isinstance(document, dict):
        raise DatasetFileError("the dataset file must be a mapping with a 'dataset' section")
    section = document.get("dataset")
    if not isinstance(section, dict):
        raise DatasetFileError("the dataset file needs a 'dataset:' section")

    unknown = sorted(str(k) for k in section if k not in _ALLOWED_KEYS)
    if unknown:
        raise DatasetFileError(
            f"unknown key(s) under dataset: {', '.join(unknown)} "
            f"(allowed: {', '.join(_ALLOWED_KEYS)})"
        )

    dataset_id = section.get("id")
    if not isinstance(dataset_id, str):
        raise DatasetFileError(
            "dataset.id is required and must be text (put quotes around it if it looks like a number)"
        )
    dataset_id = dataset_id.strip()
    if not _ID_PATTERN.match(dataset_id):
        raise DatasetFileError(
            f"dataset.id {dataset_id!r} is not valid: use 1-64 letters, digits, '_', '.' or '-', "
            "starting with a letter or digit"
        )

    name = _optional_text(section, "name")
    if not name:
        raise DatasetFileError("dataset.name is required")

    contact = section.get("contact")
    if contact is None:
        contact = {}
    elif not isinstance(contact, dict):
        raise DatasetFileError("dataset.contact must be a mapping (for example name: and email:)")

    return {
        "id": dataset_id,
        "name": name,
        "description": _optional_text(section, "description"),
        "assembly": _optional_text(section, "assembly"),
        "contact": contact,
    }


def load_dataset_file(path: str) -> Dict[str, Any]:
    """Read and validate the dataset file at ``path``."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError as e:
        raise DatasetFileError(f"dataset file not found: {path}") from e
    except OSError as e:
        raise DatasetFileError(f"cannot read dataset file {path}: {e}") from e
    return parse_dataset_text(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a dataset metadata file and print one field.")
    parser.add_argument("dataset_file")
    parser.add_argument("--get", choices=("id", "name", "assembly"), default="id",
                        help="field to print (default: id)")
    args = parser.parse_args(argv)
    try:
        meta = load_dataset_file(args.dataset_file)
    except DatasetFileError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    value = meta[args.get]
    if value is None:
        print(f"ERROR: dataset.{args.get} is not set in {args.dataset_file}", file=sys.stderr)
        return 2
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
