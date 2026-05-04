#!/usr/bin/env python3
"""
VCF to Beacon v2 Transformation Tool
Converts VCF files into Beacon v2 compliant JSON format for MongoDB storage.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
from dataclasses import dataclass, asdict

import yaml
import pandas as pd
import numpy as np
from tqdm import tqdm
import cyvcf2

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


@dataclass
class VariantRecord:
    """Data class for Beacon v2 variant record."""
    id: str
    assembly_id: str
    reference_name: str
    start: int
    end: int
    reference_bases: str
    alternate_bases: str
    variant_type: str
    annotations: List[Dict] = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.annotations is None:
            self.annotations = []


@dataclass
class IndividualRecord:
    """Data class for Beacon v2 individual record."""
    id: str
    sex: Optional[str] = None
    ethnicity: Optional[str] = None
    geographic_origin: Optional[str] = None
    age: Optional[int] = None
    diseases: Dict = None
    phenotypic_features: Dict = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.diseases is None:
            self.diseases = {}
        if self.phenotypic_features is None:
            self.phenotypic_features = {}


class VCFTransformer:
    """Main class for transforming VCF files to Beacon v2format."""

    def __init__(self, config_path: str = None):
        """Initialize the VCF transformer with configuration."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.stats = {
            'variants_processed': 0,
            'variants_filtered': 0,
            'individuals_found': 0,
            'errors': 0
        }

    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.warning(f"Config file not found: {config_path}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return default configuration if config file not found."""
        return {
            'vcf': {
                'default_assembly': 'GRCh38',
                'quality_filters': {
                    'min_qual': 20,
                    'min_depth': 10
                }
            },
            'processing': {
                'batch_size': 1000,
                'show_progress': True
            }
        }

    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('processing', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def parse_vcf(self, vcf_path: str, assembly_id: str = None) -> Iterator[Tuple[VariantRecord, str]]:
        """Parse VCF file and yield variant records."""
        if assembly_id is None:
            assembly_id = self.config['vcf']['default_assembly']

        self.logger.info(f"Starting VCF parsing: {vcf_path}")
        
        try:
            vcf = cyvcf2.VCF(vcf_path)
            total_variants = 0
            
            # Get sample names (individuals)
            samples = vcf.samples
            self.stats['individuals_found'] = len(samples)
            
            for variant in vcf:
                total_variants += 1
                
                # Apply quality filters
                if not self._passes_quality_filters(variant):
                    self.stats['variants_filtered'] += 1
                    continue

                # Create variant record
                variant_record = self._create_variant_record(variant, assembly_id)
                
                # Process each sample's genotype
                for sample_idx, sample_name in enumerate(samples):
                    genotype_info = self._extract_genotype_info(variant, sample_idx)
                    if genotype_info:
                        yield variant_record, sample_name, genotype_info

                self.stats['variants_processed'] += 1

        except Exception as e:
            self.logger.error(f"Error parsing VCF file: {e}")
            self.stats['errors'] += 1
            raise

        self.logger.info(f"VCF parsing completed. Processed {total_variants} variants")

    def _passes_quality_filters(self, variant) -> bool:
        """Check if variant passes quality filters."""
        quality_filters = self.config['vcf']['quality_filters']
        
        # Check QUAL field
        if variant.QUAL is not None and variant.QUAL < quality_filters.get('min_qual', 0):
            return False
            
        # Check depth (DP in INFO field)
        if hasattr(variant, 'INFO') and 'DP' in variant.INFO:
            if variant.INFO['DP'] < quality_filters.get('min_depth', 0):
                return False
                
        return True

    def _create_variant_record(self, variant, assembly_id: str) -> VariantRecord:
        """Create a VariantRecord from a cyvcf2 variant."""
        # Generate variant ID
        variant_id = f"{variant.CHROM}:{variant.POS}:{variant.REF}:{','.join(variant.ALT)}"
        
        # Determine variant type
        variant_type = self._determine_variant_type(variant.REF, variant.ALT)
        
        # Extract annotations
        annotations = self._extract_annotations(variant)
        
        return VariantRecord(
            id=variant_id,
            assembly_id=assembly_id,
            reference_name=str(variant.CHROM),
            start=variant.POS - 1,  # Convert to 0-based coordinates
            end=variant.POS - 1 + len(variant.REF),
            reference_bases=variant.REF,
            alternate_bases=','.join(variant.ALT) if isinstance(variant.ALT, list) else str(variant.ALT),
            variant_type=variant_type,
            annotations=annotations
        )

    def _determine_variant_type(self, ref: str, alt: List[str]) -> str:
        """Determine variant type based on REF and ALT alleles."""
        if not alt or alt[0] is None:
            return "unknown"
            
        alt_allele = alt[0]
        
        if len(ref) == len(alt_allele) == 1:
            return "SNV"  # Single Nucleotide Variant
        elif len(ref) > len(alt_allele):
            return "DEL"  # Deletion
        elif len(ref) < len(alt_allele):
            return "INS"  # Insertion
        else:
            return "COMPLEX"  # Complex variant

    def _extract_annotations(self, variant) -> List[Dict]:
        """Extract variant annotations from INFO field."""
        annotations = []
        
        if not hasattr(variant, 'INFO'):
            return annotations
            
        info = variant.INFO
        
        # Extract VEP annotations (CSQ field)
        if 'CSQ' in info:
            annotations.extend(self._parse_vep_annotations(info['CSQ']))
            
        # Extract SnpEff annotations (ANN field)
        if 'ANN' in info:
            annotations.extend(self._parse_snpeff_annotations(info['ANN']))
            
        # Extract basic annotations
        basic_annotation = {}
        for field in ['GENE', 'AF', 'AC', 'AN']:
            if field in info:
                basic_annotation[field.lower()] = info[field]
                
        if basic_annotation:
            annotations.append({
                'source': 'INFO',
                'annotations': basic_annotation
            })
            
        return annotations

    def _parse_vep_annotations(self, csq_data) -> List[Dict]:
        """Parse VEP CSQ annotations."""
        annotations = []
        # VEP CSQ format parsing would go here
        # This is a simplified version
        if isinstance(csq_data, list):
            for csq in csq_data:
                annotations.append({
                    'source': 'VEP',
                    'consequence': str(csq)
                })
        return annotations

    def _parse_snpeff_annotations(self, ann_data) -> List[Dict]:
        """Parse SnpEff ANN annotations."""
        annotations = []
        # SnpEff ANN format parsing would go here
        # This is a simplified version
        if isinstance(ann_data, list):
            for ann in ann_data:
                annotations.append({
                    'source': 'SnpEff',
                    'annotation': str(ann)
                })
        return annotations

    def _extract_genotype_info(self, variant, sample_idx: int) -> Optional[Dict]:
        """Extract genotype information for a sample."""
        try:
            gt = variant.genotypes[sample_idx]
            
            # Skip if no genotype
            if gt[0] == -1 and gt[1] == -1:
                return None
                
            genotype_info = {
                'alleles': [gt[0], gt[1]],
                'phased': bool(gt[2])
            }
            
            # Extract FORMAT fields (cyvcf2: variant.format(tag) returns ndarray per sample)
            for tag, key in (('DP', 'depth'), ('GQ', 'quality'), ('AD', 'allelic_depths')):
                try:
                    arr = variant.format(tag)
                except KeyError:
                    continue
                if arr is None:
                    continue
                try:
                    genotype_info[key] = arr[sample_idx].tolist() if hasattr(arr[sample_idx], 'tolist') else arr[sample_idx]
                except (IndexError, AttributeError):
                    pass
                    
            return genotype_info
            
        except (IndexError, KeyError) as e:
            self.logger.warning(f"Error extracting genotype info: {e}")
            return None

    def create_individuals_from_vcf(self, vcf_path: str, metadata_file: str = None) -> List[IndividualRecord]:
        """Create individual records from VCF samples."""
        individuals = []
        
        try:
            vcf = cyvcf2.VCF(vcf_path)
            samples = vcf.samples
            
            # Load additional metadata if provided
            metadata = {}
            if metadata_file and os.path.exists(metadata_file):
                metadata = self._load_individual_metadata(metadata_file)
            
            for sample_id in samples:
                individual_data = metadata.get(sample_id, {})
                
                individual = IndividualRecord(
                    id=sample_id,
                    sex=individual_data.get('sex'),
                    ethnicity=individual_data.get('ethnicity'),
                    geographic_origin=individual_data.get('geographic_origin'),
                    age=individual_data.get('age')
                )
                
                individuals.append(individual)
                
        except Exception as e:
            self.logger.error(f"Error creating individuals from VCF: {e}")
            raise
            
        return individuals

    def _load_individual_metadata(self, metadata_file: str) -> Dict:
        """Load additional individual metadata from file."""
        try:
            if metadata_file.endswith('.csv'):
                df = pd.read_csv(metadata_file)
            elif metadata_file.endswith('.tsv'):
                df = pd.read_csv(metadata_file, sep='\t')
            elif metadata_file.endswith('.xlsx'):
                df = pd.read_excel(metadata_file)
            else:
                raise ValueError(f"Unsupported metadata file format: {metadata_file}")
                
            # Convert to dictionary with sample_id as key
            metadata = {}
            for _, row in df.iterrows():
                sample_id = row.get('sample_id') or row.get('individual_id') or row.get('id')
                if sample_id:
                    metadata[sample_id] = row.to_dict()
                    
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error loading metadata file: {e}")
            return {}

    def transform_vcf_to_beacon(self, vcf_path: str, output_dir: str, 
                              assembly_id: str = None, metadata_file: str = None) -> Dict:
        """Transform VCF file to Beacon v2 format."""
        self.logger.info(f"Starting VCF transformation: {vcf_path}")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize output collections
        variants = []
        individuals = []
        variant_individual_map = {}
        
        # Process VCF file
        batch_size = self.config['processing']['batch_size']
        show_progress = self.config['processing']['show_progress']
        
        with tqdm(desc="Processing variants", disable=not show_progress) as pbar:
            for variant_record, sample_name, genotype_info in self.parse_vcf(vcf_path, assembly_id):
                # Add variant to collection
                variant_dict = asdict(variant_record)
                variants.append(variant_dict)
                
                # Track variant-individual relationships
                if variant_record.id not in variant_individual_map:
                    variant_individual_map[variant_record.id] = {}
                variant_individual_map[variant_record.id][sample_name] = genotype_info
                
                pbar.update(1)
                
                # Write in batches
                if len(variants) >= batch_size:
                    self._write_batch(variants, output_path / "variants_batch.jsonl")
                    variants = []

        # Write remaining variants
        if variants:
            self._write_batch(variants, output_path / "variants_batch.jsonl")

        # Create individuals
        individuals = self.create_individuals_from_vcf(vcf_path, metadata_file)
        individual_dicts = [asdict(ind) for ind in individuals]
        
        # Write individuals
        self._write_json_file(individual_dicts, output_path / "individuals.json")
        
        # Write variant-individual mapping
        self._write_json_file(variant_individual_map, output_path / "variant_genotypes.json")
        
        # Generate summary
        summary = {
            'transformation_date': datetime.now().isoformat(),
            'input_file': str(vcf_path),
            'output_directory': str(output_path),
            'assembly_id': assembly_id or self.config['vcf']['default_assembly'],
            'statistics': self.stats,
            'files_created': [
                'variants_batch.jsonl',
                'individuals.json',
                'variant_genotypes.json'
            ]
        }
        
        self._write_json_file(summary, output_path / "transformation_summary.json")
        
        self.logger.info(f"Transformation completed. Output written to: {output_path}")
        return summary

    def _write_batch(self, data: List[Dict], file_path: Path):
        """Write data batch to JSONL file."""
        with open(file_path, 'a') as f:
            for record in data:
                f.write(json.dumps(record) + '\n')

    def _write_json_file(self, data: any, file_path: Path):
        """Write data to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Transform VCF files to Beacon v2 format"
    )
    
    parser.add_argument(
        'vcf_file',
        help='Path to input VCF file'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output directory for transformed data'
    )
    
    parser.add_argument(
        '-a', '--assembly',
        default='GRCh38',
        help='Genome assembly ID (default: GRCh38)'
    )
    
    parser.add_argument(
        '-m', '--metadata',
        help='Path to individual metadata file (CSV/TSV/XLSX)'
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Initialize transformer
    transformer = VCFTransformer(args.config)
    
    try:
        # Transform VCF
        summary = transformer.transform_vcf_to_beacon(
            vcf_path=args.vcf_file,
            output_dir=args.output,
            assembly_id=args.assembly,
            metadata_file=args.metadata
        )
        
        print("VCF transformation completed successfully!")
        print(f"Statistics: {summary['statistics']}")
        print(f"Output files: {summary['files_created']}")
        
    except Exception as e:
        print(f"Error during transformation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 