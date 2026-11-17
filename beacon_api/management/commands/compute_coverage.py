"""
Store what each dataset can serve (chromosomes held, allele frequencies present)
on the Dataset document, for /api/datasets to report.

Read-only on variants; the only write is ``Dataset.coverage``. Prints what it
found and writes nothing unless ``--apply`` is given. Chromosomes come from a
``distinct`` on ``reference_name``; allele frequencies count as present only
when a variant with a non-null ``allele_frequency`` exists.

Every read is bounded by ``--max-time-seconds`` (default 60) and goes straight
through pymongo, where the cap is enforced by the server. The frequency check
has no usable index: when no variant has a frequency it must look at every
document (about 42 million in production), which is a long scan on the live
database. A query that hits the cap aborts the command with nothing written,
because "did not finish" is not the same answer as "no frequencies".

Variants are matched to a dataset through ``dataset_ids``; when no variant
carries ``dataset_ids`` (the single-dataset production layout) the whole
collection is taken to belong to the only dataset, and the command refuses if
there is more than one.
"""

from django.core.management.base import BaseCommand, CommandError
from pymongo.errors import ExecutionTimeout

from beacon_api.models import Dataset, Variant


class Command(BaseCommand):
    help = "Compute and store per-dataset coverage (dry run unless --apply)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Write Dataset.coverage"
        )
        parser.add_argument(
            "--max-time-seconds",
            type=int,
            default=60,
            help="Server-side cap for each read (default 60). Raise it to scan a large collection.",
        )

    def _bounded(self, what, read):
        try:
            return read()
        except ExecutionTimeout:
            raise CommandError(
                f"{what} did not finish within the time cap, so nothing was written. "
                f"Raise --max-time-seconds if the collection is that large."
            )

    def handle(self, *args, **options):
        datasets = list(Dataset.objects.all())
        if not datasets:
            raise CommandError("No datasets in the catalogue.")
        cap_ms = options["max_time_seconds"] * 1000
        collection = Variant._get_collection()
        only_id = {"_id": 1}
        for ds in datasets:
            owned = {"dataset_ids": ds.id}
            if (
                self._bounded(
                    f"Looking for a variant of {ds.id}",
                    lambda: collection.find_one(owned, only_id, max_time_ms=cap_ms),
                )
                is not None
            ):
                match = owned
            elif len(datasets) == 1:
                match = {}
            else:
                raise CommandError(
                    f"Dataset {ds.id}: no variant carries its id and there are "
                    f"{len(datasets)} datasets, so ownership cannot be inferred."
                )
            chromosomes = sorted(
                self._bounded(
                    f"Listing the chromosomes of {ds.id}",
                    lambda: collection.distinct(
                        "reference_name", match, maxTimeMS=cap_ms
                    ),
                )
            )
            with_frequency = dict(match, allele_frequency={"$ne": None})
            has_af = (
                self._bounded(
                    f"Looking for an allele frequency in {ds.id}",
                    lambda: collection.find_one(
                        with_frequency, only_id, max_time_ms=cap_ms
                    ),
                )
                is not None
            )
            coverage = {"chromosomes": chromosomes, "alleleFrequency": has_af}
            self.stdout.write(f"{ds.id}: {coverage}")
            if options["apply"]:
                ds.coverage = coverage
                ds.save()
        if not options["apply"]:
            self.stdout.write("Dry run: nothing written. Re-run with --apply.")
