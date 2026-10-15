"""
Register a dataset in the ``datasets`` collection so ``/datasets`` lists it.

Importing variants fills the ``variants`` collection but creates no dataset
record, so a loaded dataset was invisible to ``/datasets`` until someone inserted
the record by hand. This reads a dataset metadata file (see ``dataset_file.py``)
and upserts that record, with the variant count taken from the database itself::

    python register_dataset.py dataset.yaml --db beacon_db \\
        --mongo-uri mongodb://localhost:27017/ --samples 9

Run it AFTER importing the variants. It refuses to register a dataset that no
variant carries the id of, because that record would list a dataset containing
nothing. Running it again updates the same record.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Run as `python path/to/register_dataset.py`, the package root is not on the path
# (the container sets PYTHONPATH, a plain Python environment does not).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_import.dataset_file import DatasetFileError, load_dataset_file  # noqa: E402


def build_dataset_update(
    meta: Dict[str, Any],
    variants: Optional[int],
    samples: Optional[int],
    now: datetime,
    default_assembly: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return the (filter, update) pair that upserts the dataset record."""
    assembly = meta.get("assembly") or default_assembly
    if not assembly:
        raise ValueError(
            "no assembly: set dataset.assembly in the dataset file or pass --assembly"
        )

    fields: Dict[str, Any] = {
        "name": meta["name"],
        "assembly_id": assembly,
        "dataset_type": "genomics",
        "contact_info": meta.get("contact") or {},
        "update_date": now,
    }
    if meta.get("description") is not None:
        fields["description"] = meta["description"]

    # Integers on purpose: the API shows variantCount/sampleCount only when they
    # are ints, and a float (what the Mongo shell stores) is silently dropped.
    # A count that is not known is left out, not written as 0.
    size = {}
    if variants is not None:
        size["variants"] = int(variants)
    if samples is not None:
        size["samples"] = int(samples)
    if size:
        fields["dataset_size"] = size

    return {"_id": meta["id"]}, {"$set": fields, "$setOnInsert": {"create_date": now}}


def register_dataset(db, meta, samples=None, now=None, default_assembly=None):
    """Upsert the dataset record into ``db`` and return the fields written."""
    dataset_id = meta["id"]
    variants = db["variants"].count_documents({"dataset_ids": dataset_id})
    if variants == 0:
        raise ValueError(
            f"no variants in the database carry dataset id {dataset_id!r}; import the variants "
            "with that --dataset-id first, otherwise this dataset would list nothing"
        )
    filt, update = build_dataset_update(
        meta, variants, samples, now or datetime.now(), default_assembly
    )
    db["datasets"].update_one(filt, update, upsert=True)
    return update["$set"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Register a dataset record from a dataset metadata file.")
    parser.add_argument("dataset_file")
    parser.add_argument("--db", required=True, help="MongoDB database name")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017/")
    parser.add_argument("--samples", type=int, help="number of samples in the dataset")
    parser.add_argument("--assembly", help="used when the dataset file sets no assembly")
    args = parser.parse_args(argv)

    try:
        meta = load_dataset_file(args.dataset_file)
    except DatasetFileError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        written = register_dataset(
            client[args.db], meta, samples=args.samples, default_assembly=args.assembly
        )
    except (ValueError, PyMongoError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()

    size = written.get("dataset_size", {})
    print(f"Registered dataset {meta['id']!r} ({written['name']}): "
          f"{size.get('variants', '?')} variants, {size.get('samples', '?')} samples")
    return 0


if __name__ == "__main__":
    sys.exit(main())
