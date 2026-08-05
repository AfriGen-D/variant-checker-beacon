"""
Create the MongoDB indexes declared on the MongoEngine models.

Every model sets ``auto_create_index: False``, so declaring an index in
``meta['indexes']`` builds nothing on its own — the indexes have to be created
explicitly. ``docs/TESTING.md`` has told operators to run
``manage.py create_indexes`` for a while; this is that command.

Safe to re-run: ``Document.ensure_indexes()`` is idempotent, and existing
indexes are left untouched. Nothing is ever dropped.
"""
from django.core.management.base import BaseCommand

from beacon_api.models import (
    Analysis,
    Biosample,
    Cohort,
    Dataset,
    FilteringTerm,
    Individual,
    QueryLog,
    Variant,
    VariantInDataset,
)

MODELS = [
    Variant,
    Individual,
    Dataset,
    Biosample,
    Analysis,
    Cohort,
    VariantInDataset,
    FilteringTerm,
    QueryLog,
]


class Command(BaseCommand):
    help = 'Create the MongoDB indexes declared on the beacon_api models (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report which indexes are missing without creating them',
        )
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            help='Only process this model (by class name, e.g. Variant)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        only = options['model']

        models = MODELS
        if only:
            models = [m for m in MODELS if m.__name__.lower() == only.lower()]
            if not models:
                self.stderr.write(self.style.ERROR(
                    f'Unknown model {only!r}. Known: {", ".join(m.__name__ for m in MODELS)}'
                ))
                return

        total_created = 0
        total_existing = 0
        failures = 0

        for model in models:
            collection_name = model._meta.get('collection', model.__name__.lower())
            try:
                collection = model._get_collection()
                before = set(collection.index_information())
            except Exception as e:
                failures += 1
                self.stderr.write(self.style.ERROR(
                    f'{model.__name__}: could not read indexes on "{collection_name}": {e}'
                ))
                continue

            if dry_run:
                # Compare declared specs against what exists, by name where the
                # declaration provides one.
                declared = self._declared_index_names(model)
                missing = sorted(declared - before)
                if missing:
                    self.stdout.write(
                        f'{model.__name__} ({collection_name}): would create {", ".join(missing)}'
                    )
                else:
                    self.stdout.write(
                        f'{model.__name__} ({collection_name}): up to date'
                    )
                continue

            try:
                model.ensure_indexes()
                after = set(collection.index_information())
            except Exception as e:
                failures += 1
                self.stderr.write(self.style.ERROR(
                    f'{model.__name__}: index creation failed on "{collection_name}": {e}'
                ))
                continue

            created = sorted(after - before)
            total_created += len(created)
            total_existing += len(before)

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'{model.__name__} ({collection_name}): created {len(created)} '
                    f'index(es) -> {", ".join(created)}'
                ))
            else:
                self.stdout.write(
                    f'{model.__name__} ({collection_name}): no new indexes '
                    f'({len(before)} already present)'
                )

        if dry_run:
            return

        summary = f'Done. {total_created} index(es) created, {total_existing} already present.'
        if failures:
            self.stderr.write(self.style.ERROR(f'{summary} {failures} model(s) failed.'))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _declared_index_names(model):
        """Names of declared indexes that carry an explicit 'name'.

        MongoDB auto-generates names for unnamed specs (e.g. 'start_1'), which
        we cannot reliably predict here, so --dry-run only reports on the
        explicitly named ones.
        """
        names = set()
        for spec in model._meta.get('indexes', []):
            if isinstance(spec, dict) and spec.get('name'):
                names.add(spec['name'])
        return names
