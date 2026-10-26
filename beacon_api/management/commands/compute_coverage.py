"""
Store what each dataset can serve (chromosomes held, allele frequencies present)
on the Dataset document, for /api/datasets to report.

Read-only on variants; the only write is ``Dataset.coverage``. Prints what it
found and writes nothing unless ``--apply`` is given. Chromosomes come from an
indexed ``distinct`` on ``reference_name``; allele frequencies count as present
only when a variant with a non-null ``allele_frequency`` exists.

Variants are matched to a dataset through ``dataset_ids``; when no variant
carries ``dataset_ids`` (the single-dataset production layout) the whole
collection is taken to belong to the only dataset, and the command refuses if
there is more than one.
"""
from django.core.management.base import BaseCommand, CommandError

from beacon_api.models import Dataset, Variant


class Command(BaseCommand):
    help = 'Compute and store per-dataset coverage (dry run unless --apply)'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write Dataset.coverage')

    def handle(self, *args, **options):
        datasets = list(Dataset.objects.all())
        if not datasets:
            raise CommandError('No datasets in the catalogue.')
        for ds in datasets:
            scoped = Variant.objects(dataset_ids=ds.id)
            if scoped.limit(1).first() is not None:
                variants = scoped
            elif len(datasets) == 1:
                variants = Variant.objects
            else:
                raise CommandError(
                    f'Dataset {ds.id}: no variant carries its id and there are '
                    f'{len(datasets)} datasets, so ownership cannot be inferred.')
            chromosomes = sorted(variants.distinct('reference_name'))
            has_af = variants(allele_frequency__ne=None).limit(1).first() is not None
            coverage = {'chromosomes': chromosomes, 'alleleFrequency': has_af}
            self.stdout.write(f'{ds.id}: {coverage}')
            if options['apply']:
                ds.coverage = coverage
                ds.save()
        if not options['apply']:
            self.stdout.write('Dry run: nothing written. Re-run with --apply.')
