import os
import json
from django.core.management.base import BaseCommand
from beacon_api.models import Variant, Dataset, Individual, VariantInDataset, VariantAnnotation


class Command(BaseCommand):
    help = 'Import variants from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the JSON file containing variants')
        parser.add_argument('--dataset', type=str, required=True, help='Dataset ID to associate variants with')

    def handle(self, *args, **options):
        file_path = options['file_path']
        dataset_id = options['dataset']

        # Check if file exists
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} does not exist'))
            return

        # Check if dataset exists
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Dataset {dataset_id} does not exist'))
            return

        # Load variants from file
        try:
            with open(file_path, 'r') as f:
                variants_data = json.load(f)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f'Invalid JSON format in {file_path}'))
            return

        # Import variants
        variants_created = 0
        variants_updated = 0
        individuals_created = 0

        for variant_data in variants_data:
            # Extract variant fields
            variant_id = variant_data.get('id')
            if not variant_id:
                self.stdout.write(self.style.WARNING('Skipping variant without ID'))
                continue

            # Create or update variant
            variant_fields = {
                'assembly_id': variant_data.get('assemblyId'),
                'reference_name': variant_data.get('referenceName'),
                'start': variant_data.get('start'),
                'end': variant_data.get('end'),
                'reference_bases': variant_data.get('referenceBases'),
                'alternate_bases': variant_data.get('alternateBases'),
                'variant_type': variant_data.get('variantType', 'unknown')
            }

            # Check for required fields
            if not all([variant_fields['assembly_id'], variant_fields['reference_name'], 
                       variant_fields['start'], variant_fields['reference_bases']]):
                self.stdout.write(self.style.WARNING(f'Skipping variant {variant_id} due to missing required fields'))
                continue

            variant, created = Variant.objects.update_or_create(
                id=variant_id, defaults=variant_fields
            )

            if created:
                variants_created += 1
            else:
                variants_updated += 1

            # Process annotations if present
            annotations = variant_data.get('annotations', [])
            for ann in annotations:
                VariantAnnotation.objects.update_or_create(
                    variant=variant,
                    gene_id=ann.get('geneId'),
                    defaults={
                        'gene_symbol': ann.get('geneSymbol'),
                        'molecular_consequence': ann.get('molecularConsequence'),
                        'clinical_significance': ann.get('clinicalSignificance'),
                        'additional_annotations': ann.get('additionalAnnotations', {})
                    }
                )

            # Process individual data if present
            individual_data = variant_data.get('individual')
            individual = None
            if individual_data and individual_data.get('id'):
                individual, ind_created = Individual.objects.update_or_create(
                    id=individual_data.get('id'),
                    defaults={
                        'sex': individual_data.get('sex'),
                        'ethnicity': individual_data.get('ethnicity'),
                        'geographic_origin': individual_data.get('geographicOrigin'),
                        'age': individual_data.get('age')
                    }
                )
                if ind_created:
                    individuals_created += 1

            # Create variant in dataset
            VariantInDataset.objects.update_or_create(
                variant=variant,
                dataset=dataset,
                individual=individual,
                defaults={
                    'genotype': variant_data.get('genotype'),
                    'allele_frequency': variant_data.get('alleleFrequency')
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f'Successfully imported: {variants_created} new variants, {variants_updated} updated variants, '
            f'{individuals_created} new individuals'
        )) 