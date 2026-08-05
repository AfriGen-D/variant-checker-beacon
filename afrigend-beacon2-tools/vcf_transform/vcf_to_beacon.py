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
    # Datasets this variant belongs to. The API filters on `dataset_ids` to
    # attribute a hit (and its allele frequency) to a dataset, so a record
    # without it is invisible per-dataset.
    dataset_ids: List[str] = None
    annotations: List[Dict] = None
    allele_frequency: float = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.annotations is None:
            self.annotations = []
        if self.dataset_ids is None:
            self.dataset_ids = []


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

    def __init__(self, config_path: str = None, dataset_id: str = None):
        """Initialize the VCF transformer with configuration.

        `dataset_id` is the Beacon dataset every variant from this VCF belongs
        to. It falls back to `dataset.id` in the config file so a pipeline that
        only passes --config can still attribute its variants.
        """
        self.config = self._load_config(config_path)
        self.dataset_id = dataset_id or (self.config.get('dataset') or {}).get('id')
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

    def parse_vcf(self, vcf_path: str, assembly_id: str = None) -> Iterator[VariantRecord]:
        """Parse VCF file and yield variant records (no per-sample genotype extraction)."""
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

                # One record per ALT allele. A multi-allelic site written as a
                # single "T,G" document can never match an exact-allele query
                # and would carry ALT-1's frequency on the joined string.
                for alt_index in range(max(1, len(self._alt_alleles(variant)))):
                    yield self._create_variant_record(variant, assembly_id, alt_index)
                    self.stats['variants_processed'] += 1

        except Exception as e:
            self.logger.error(f"Error parsing VCF file: {e}")
            self.stats['errors'] += 1
            raise

        self.logger.info(f"VCF parsing completed. Total: {total_variants}, passed filters: {self.stats['variants_processed']}")

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

    @staticmethod
    def _alt_alleles(variant) -> List[str]:
        """Return the site's ALT alleles as a list of strings."""
        alt = getattr(variant, 'ALT', None)
        if alt is None:
            return []
        if isinstance(alt, (list, tuple)):
            return [str(a) for a in alt if a is not None]
        return [str(alt)]

    @staticmethod
    def _per_allele_value(value, alt_index: int):
        """Narrow a per-ALT INFO value (AF, AC, ...) to a single ALT allele.

        A sequence carries one entry per ALT; anything shorter than alt_index+1
        is treated as absent rather than mispaired with the wrong allele. A
        scalar describes only the first ALT.
        """
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return value[alt_index] if alt_index < len(value) else None
        return value if alt_index == 0 else None

    def _create_variant_record(self, variant, assembly_id: str,
                               alt_index: int = 0) -> VariantRecord:
        """Create a VariantRecord for one ALT allele of a cyvcf2 variant."""
        alts = self._alt_alleles(variant)
        alt_allele = alts[alt_index] if alt_index < len(alts) else ''

        # Natural key — unique per emitted allele, not per site
        variant_id = f"{variant.CHROM}:{variant.POS}:{variant.REF}:{alt_allele}"

        # Determine variant type for this allele specifically
        variant_type = self._determine_variant_type(variant.REF, [alt_allele])

        # Extract annotations, with AF/AC narrowed to this allele
        annotations = self._extract_annotations(variant, alt_index)

        # Aggregate allele frequency, given a queryable home (not just the blob)
        allele_frequency = self._extract_allele_frequency(variant, alt_index)

        return VariantRecord(
            id=variant_id,
            assembly_id=assembly_id,
            reference_name=str(variant.CHROM),
            start=variant.POS - 1,  # Convert to 0-based coordinates
            end=variant.POS - 1 + len(variant.REF),
            reference_bases=variant.REF,
            alternate_bases=alt_allele,
            variant_type=variant_type,
            dataset_ids=[self.dataset_id] if self.dataset_id else [],
            annotations=annotations,
            allele_frequency=allele_frequency,
        )

    @classmethod
    def _extract_allele_frequency(cls, variant, alt_index: int = 0) -> float:
        """Return this ALT allele's AF from the VCF INFO field as a float, or None.

        cyvcf2's INFO exposes `.get(key)`; for a multi-allelic site AF is a
        tuple/list with one entry per ALT, so it is indexed by alt_index.
        """
        if not hasattr(variant, 'INFO'):
            return None
        af = cls._per_allele_value(variant.INFO.get('AF'), alt_index)
        try:
            return float(af) if af is not None else None
        except (TypeError, ValueError):
            return None

    def _determine_variant_type(self, ref: str, alt: List[str]) -> str:
        """Determine variant type based on REF and ALT alleles."""
        if not alt or not alt[0]:
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

    def _extract_annotations(self, variant, alt_index: int = 0) -> List[Dict]:
        """Extract variant annotations from INFO field for one ALT allele."""
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
            
        # Extract basic annotations. Use INFO.get(): cyvcf2's INFO object is not
        # a dict and does not support `in`/subscript reliably, so the previous
        # `field in info` / `info[field]` form silently extracted nothing.
        # AF and AC are per-ALT, so they are narrowed to the allele this record
        # describes; GENE and AN are site-level and kept whole.
        basic_annotation = {}
        for field in ['GENE', 'AF', 'AC', 'AN']:
            val = info.get(field)
            if field in ('AF', 'AC'):
                val = self._per_allele_value(val, alt_index)
            if val is not None:
                basic_annotation[field.lower()] = val
                
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
            
            # Extract FORMAT fields (cyvcf2: variant.format(field) returns numpy array)
            try:
                dp = variant.format('DP')
                if dp is not None:
                    genotype_info['depth'] = int(dp[sample_idx][0])
            except (KeyError, IndexError):
                pass
            try:
                gq = variant.format('GQ')
                if gq is not None:
                    genotype_info['quality'] = int(gq[sample_idx][0])
            except (KeyError, IndexError):
                pass
            try:
                ad = variant.format('AD')
                if ad is not None:
                    genotype_info['allelic_depths'] = ad[sample_idx].tolist()
            except (KeyError, IndexError):
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
        
        # Process VCF — variant-level only (no per-sample genotypes for Boolean mode)
        variants = []
        batch_size = self.config['processing']['batch_size']
        show_progress = self.config['processing']['show_progress']

        with tqdm(desc="Processing variants", disable=not show_progress) as pbar:
            for variant_record in self.parse_vcf(vcf_path, assembly_id):
                variants.append(asdict(variant_record))
                pbar.update(1)

                if len(variants) >= batch_size:
                    self._write_batch(variants, output_path / "variants_batch.jsonl")
                    variants = []

        if variants:
            self._write_batch(variants, output_path / "variants_batch.jsonl")

        # Create individuals list from VCF header (no genotype data)
        individuals = self.create_individuals_from_vcf(vcf_path, metadata_file)
        self._write_json_file([asdict(ind) for ind in individuals], output_path / "individuals.json")

        # Write empty genotypes file (placeholder for Secure mode later)
        self._write_json_file([], output_path / "variant_genotypes.json")
        
        # Generate summary
        summary = {
            'transformation_date': datetime.now().isoformat(),
            'input_file': str(vcf_path),
            'output_directory': str(output_path),
            'assembly_id': assembly_id or self.config['vcf']['default_assembly'],
            'dataset_id': self.dataset_id,
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
        '-d', '--dataset-id',
        help='Beacon dataset ID these variants belong to '
             '(defaults to dataset.id in the config file)'
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
    transformer = VCFTransformer(args.config, dataset_id=args.dataset_id)
    
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