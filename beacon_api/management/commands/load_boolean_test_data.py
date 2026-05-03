"""
Management command to load test data for Boolean mode testing
"""
from django.core.management.base import BaseCommand
from beacon_api.models import Variant, Individual, Dataset
import random
from datetime import datetime

class Command(BaseCommand):
    help = 'Load sample test data for Boolean mode testing'

    def handle(self, *args, **options):
        self.stdout.write('Loading test data for Boolean mode...')
        
        # Clear existing data
        Variant.objects.delete()
        Individual.objects.delete()
        Dataset.objects.delete()
        
        # Create test dataset
        dataset = Dataset(
            id='test_dataset_001',
            name='Test Dataset for Boolean Mode',
            description='Sample data for testing Boolean responses',
            assembly_id='GRCh38',
            dataset_type='genomics',
            dataset_size={'variants': 100, 'samples': 50},
            contact_info={'email': 'beacon@afrigen-d.org'}
        )
        dataset.save()
        self.stdout.write(f'Created dataset: {dataset.id}')
        
        # Create test variants
        chromosomes = ['1', '2', '3', '4', '5', '10', '15', '20', 'X', 'Y']
        bases = ['A', 'C', 'G', 'T']
        
        variants_created = 0
        for chrom in chromosomes:
            for i in range(10):  # 10 variants per chromosome
                position = random.randint(1000000, 50000000)
                ref = random.choice(bases)
                alt = random.choice([b for b in bases if b != ref])
                
                variant = Variant(
                    id=f'var_{chrom}_{position}_{ref}_{alt}',
                    assembly_id='GRCh38',
                    reference_name=f'chr{chrom}',
                    start=position,
                    end=position + 1,
                    reference_bases=ref,
                    alternate_bases=alt,
                    variant_type='SNP'
                )
                variant.save()
                variants_created += 1
        
        self.stdout.write(f'Created {variants_created} test variants')
        
        # Create test individuals
        sexes = ['MALE', 'FEMALE', 'OTHER', 'UNKNOWN']
        diseases = ['NCIT:C3058', 'NCIT:C3059', 'NCIT:C2985', 'NCIT:C3262']
        
        individuals_created = 0
        for i in range(50):
            individual = Individual(
                id=f'ind_{i:04d}',
                sex=random.choice(sexes),
                ethnicity=random.choice(['European', 'African', 'Asian', 'American']),
                geographic_origin=random.choice(['USA', 'UK', 'France', 'Germany', 'Japan'])
            )
            individual.save()
            individuals_created += 1
        
        self.stdout.write(f'Created {individuals_created} test individuals')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nTest data loaded successfully:\n'
            f'  - Datasets: 1\n'
            f'  - Variants: {variants_created}\n'
            f'  - Individuals: {individuals_created}\n'
            f'\nYou can now test Boolean queries!'
        ))
        
        # Example queries to test
        self.stdout.write('\nExample test queries:')
        self.stdout.write('  curl "http://localhost:8000/api/g_variants?referenceName=1&start=1000000&end=50000000"')
        self.stdout.write('  curl "http://localhost:8000/api/individuals?sex=MALE"')
        self.stdout.write('  curl "http://localhost:8000/api/individuals?diseaseCode=NCIT:C3058"')