#!/usr/bin/env python3
"""
Phenotype to Beacon v2 Transformation Tool
Converts phenotypic data into Beacon v2 compliant format with ontology mapping.
"""

import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict

import yaml
import pandas as pd
import numpy as np
from tqdm import tqdm
import pronto

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


@dataclass
class PhenotypeRecord:
    """Data class for phenotype record."""
    individual_id: str
    phenotype_id: str
    phenotype_label: str
    ontology: str
    observed: bool = True
    age_of_onset: Optional[str] = None
    severity: Optional[str] = None
    modifiers: List[str] = None
    evidence: Optional[Dict] = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.modifiers is None:
            self.modifiers = []


@dataclass
class DiseaseRecord:
    """Data class for disease record."""
    individual_id: str
    disease_id: str
    disease_label: str
    ontology: str
    age_of_onset: Optional[str] = None
    stage: Optional[str] = None
    family_history: bool = False
    notes: Optional[str] = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()


class OntologyManager:
    """Manages ontology lookups and mappings."""

    def __init__(self, config: Dict):
        self.config = config
        self.ontologies = {}
        self.cache = {}
        self.logger = logging.getLogger(__name__)

    def load_ontology(self, ontology_name: str) -> Optional[pronto.Ontology]:
        """Load ontology from file or URL."""
        if ontology_name in self.ontologies:
            return self.ontologies[ontology_name]

        try:
            ontology_path = self._get_ontology_path(ontology_name)
            if ontology_path:
                ontology = pronto.Ontology(ontology_path)
                self.ontologies[ontology_name] = ontology
                self.logger.info(f"Loaded ontology: {ontology_name}")
                return ontology
        except Exception as e:
            self.logger.error(f"Failed to load ontology {ontology_name}: {e}")

        return None

    def _get_ontology_path(self, ontology_name: str) -> Optional[str]:
        """Get path or URL for ontology."""
        ontology_sources = {
            'HPO': 'https://raw.githubusercontent.com/obophenotype/human-phenotype-ontology/master/hp.obo',
            'MONDO': 'https://raw.githubusercontent.com/monarch-initiative/mondo/master/mondo.obo',
            'ORDO': 'https://raw.githubusercontent.com/Orphanet/ORDO/master/ordo.obo'
        }
        
        return ontology_sources.get(ontology_name.upper())

    def lookup_term(self, term_id: str, ontology_name: str = None) -> Optional[Dict]:
        """Look up term information from ontology."""
        cache_key = f"{ontology_name}:{term_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Try to determine ontology from term ID if not provided
        if ontology_name is None:
            ontology_name = self._infer_ontology_from_id(term_id)

        if ontology_name:
            ontology = self.load_ontology(ontology_name)
            if ontology and term_id in ontology:
                term = ontology[term_id]
                term_info = {
                    'id': term_id,
                    'label': term.name,
                    'definition': term.definition,
                    'synonyms': [str(syn) for syn in term.synonyms],
                    'ontology': ontology_name,
                    'is_obsolete': term.obsolete
                }
                self.cache[cache_key] = term_info
                return term_info

        # Fallback to API lookup
        return self._api_lookup(term_id, ontology_name)

    def _infer_ontology_from_id(self, term_id: str) -> Optional[str]:
        """Infer ontology from term ID prefix."""
        if term_id.startswith('HP:'):
            return 'HPO'
        elif term_id.startswith('MONDO:'):
            return 'MONDO'
        elif term_id.startswith('ORDO:'):
            return 'ORDO'
        elif term_id.startswith('NCIT:'):
            return 'NCIT'
        return None

    def _api_lookup(self, term_id: str, ontology_name: str) -> Optional[Dict]:
        """Lookup term via API as fallback."""
        try:
            if ontology_name == 'HPO':
                url = f"https://hpo.jax.org/api/hpo/term/{term_id}"
            elif ontology_name == 'MONDO':
                url = f"https://www.ebi.ac.uk/ols/api/ontologies/mondo/terms/{term_id.replace(':', '%3A')}"
            else:
                return None

            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self._parse_api_response(data, ontology_name)

        except Exception as e:
            self.logger.warning(f"API lookup failed for {term_id}: {e}")

        return None

    def _parse_api_response(self, data: Dict, ontology_name: str) -> Dict:
        """Parse API response to standard format."""
        if ontology_name == 'HPO':
            return {
                'id': data.get('id'),
                'label': data.get('name'),
                'definition': data.get('definition'),
                'synonyms': data.get('synonyms', []),
                'ontology': 'HPO',
                'is_obsolete': data.get('isObsolete', False)
            }
        elif ontology_name == 'MONDO':
            return {
                'id': data.get('obo_id'),
                'label': data.get('label'),
                'definition': data.get('description', [None])[0] if data.get('description') else None,
                'synonyms': [syn.get('label') for syn in data.get('synonyms', [])],
                'ontology': 'MONDO',
                'is_obsolete': data.get('is_obsolete', False)
            }
        return {}


class PhenotypeTransformer:
    """Main class for transforming phenotypic data to Beacon v2 format."""

    def __init__(self, config_path: str = None):
        """Initialize the phenotype transformer."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.ontology_manager = OntologyManager(self.config)
        self.stats = {
            'phenotypes_processed': 0,
            'diseases_processed': 0,
            'individuals_processed': 0,
            'ontology_lookups': 0,
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
        """Return default configuration."""
        return {
            'phenotypes': {
                'default_ontology': 'HPO',
                'supported_formats': ['csv', 'tsv', 'xlsx', 'json']
            },
            'processing': {
                'batch_size': 1000,
                'show_progress': True,
                'log_level': 'INFO'
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

    def load_phenotype_data(self, file_path: str) -> pd.DataFrame:
        """Load phenotype data from various file formats."""
        file_path = Path(file_path)
        
        try:
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_path.suffix.lower() == '.tsv':
                df = pd.read_csv(file_path, sep='\t')
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == '.json':
                df = pd.read_json(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
                
            self.logger.info(f"Loaded {len(df)} records from {file_path}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading phenotype data: {e}")
            raise

    def normalize_phenotype_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize phenotype data columns."""
        # Define column mappings
        column_mappings = {
            'individual_id': ['individual_id', 'sample_id', 'patient_id', 'subject_id', 'id'],
            'phenotype_id': ['phenotype_id', 'hpo_id', 'term_id', 'phenotype_code'],
            'phenotype_label': ['phenotype_label', 'phenotype_name', 'phenotype', 'term_name', 'label'],
            'ontology': ['ontology', 'source', 'vocabulary'],
            'observed': ['observed', 'present', 'status'],
            'age_of_onset': ['age_of_onset', 'onset_age', 'age_onset'],
            'severity': ['severity', 'severity_score'],
            'disease_id': ['disease_id', 'mondo_id', 'ordo_id', 'disease_code'],
            'disease_label': ['disease_label', 'disease_name', 'disease', 'diagnosis']
        }

        # Create normalized DataFrame
        normalized_df = df.copy()
        
        for standard_col, possible_cols in column_mappings.items():
            for col in possible_cols:
                if col in df.columns:
                    if standard_col not in normalized_df.columns:
                        normalized_df[standard_col] = df[col]
                    break

        # Handle boolean conversion for 'observed' column
        if 'observed' in normalized_df.columns:
            normalized_df['observed'] = normalized_df['observed'].map({
                'true': True, 'True': True, 'TRUE': True, 1: True, '1': True,
                'false': False, 'False': False, 'FALSE': False, 0: False, '0': False,
                'yes': True, 'Yes': True, 'YES': True,
                'no': False, 'No': False, 'NO': False,
                'present': True, 'absent': False, 'negative': False, 'positive': True
            }).fillna(True)  # Default to True if unknown

        self.logger.info(f"Normalized DataFrame with columns: {list(normalized_df.columns)}")
        return normalized_df

    def transform_phenotypes(self, df: pd.DataFrame) -> List[PhenotypeRecord]:
        """Transform phenotype data to Beacon v2 format."""
        phenotype_records = []
        
        # Filter rows that have phenotype information
        phenotype_df = df[df['phenotype_id'].notna()]
        
        for _, row in tqdm(phenotype_df.iterrows(), 
                          total=len(phenotype_df), 
                          desc="Processing phenotypes",
                          disable=not self.config['processing']['show_progress']):
            
            try:
                # Get ontology information
                ontology = row.get('ontology', self.config['phenotypes']['default_ontology'])
                phenotype_id = str(row['phenotype_id']).strip()
                
                # Lookup term information
                term_info = self.ontology_manager.lookup_term(phenotype_id, ontology)
                if term_info:
                    self.stats['ontology_lookups'] += 1
                    phenotype_label = term_info['label']
                    ontology = term_info['ontology']
                else:
                    phenotype_label = row.get('phenotype_label', phenotype_id)

                # Create phenotype record
                phenotype_record = PhenotypeRecord(
                    individual_id=str(row['individual_id']),
                    phenotype_id=phenotype_id,
                    phenotype_label=phenotype_label,
                    ontology=ontology,
                    observed=bool(row.get('observed', True)),
                    age_of_onset=row.get('age_of_onset'),
                    severity=row.get('severity'),
                    modifiers=self._parse_list_field(row.get('modifiers')),
                    evidence=self._create_evidence_dict(row)
                )
                
                phenotype_records.append(phenotype_record)
                self.stats['phenotypes_processed'] += 1

            except Exception as e:
                self.logger.error(f"Error processing phenotype row: {e}")
                self.stats['errors'] += 1

        return phenotype_records

    def transform_diseases(self, df: pd.DataFrame) -> List[DiseaseRecord]:
        """Transform disease data to Beacon v2 format."""
        disease_records = []
        
        # Filter rows that have disease information
        disease_df = df[df['disease_id'].notna()]
        
        for _, row in tqdm(disease_df.iterrows(), 
                          total=len(disease_df), 
                          desc="Processing diseases",
                          disable=not self.config['processing']['show_progress']):
            
            try:
                # Get ontology information
                ontology = row.get('ontology', 'MONDO')
                disease_id = str(row['disease_id']).strip()
                
                # Lookup term information
                term_info = self.ontology_manager.lookup_term(disease_id, ontology)
                if term_info:
                    self.stats['ontology_lookups'] += 1
                    disease_label = term_info['label']
                    ontology = term_info['ontology']
                else:
                    disease_label = row.get('disease_label', disease_id)

                # Create disease record
                disease_record = DiseaseRecord(
                    individual_id=str(row['individual_id']),
                    disease_id=disease_id,
                    disease_label=disease_label,
                    ontology=ontology,
                    age_of_onset=row.get('age_of_onset'),
                    stage=row.get('stage'),
                    family_history=bool(row.get('family_history', False)),
                    notes=row.get('notes')
                )
                
                disease_records.append(disease_record)
                self.stats['diseases_processed'] += 1

            except Exception as e:
                self.logger.error(f"Error processing disease row: {e}")
                self.stats['errors'] += 1

        return disease_records

    def _parse_list_field(self, field_value) -> List[str]:
        """Parse list field from various formats."""
        if field_value is None:
            return []

        if isinstance(field_value, list):
            return [str(item) for item in field_value]

        if pd.isna(field_value):
            return []
        
        if isinstance(field_value, str):
            # Try to parse as comma-separated values
            return [item.strip() for item in field_value.split(',') if item.strip()]
        
        return [str(field_value)]

    def _create_evidence_dict(self, row: pd.Series) -> Optional[Dict]:
        """Create evidence dictionary from available data."""
        evidence = {}
        
        # Add evidence fields if available
        evidence_fields = ['evidence_code', 'publication', 'date_observed', 'observer']
        for field in evidence_fields:
            if field in row and pd.notna(row[field]):
                evidence[field] = row[field]
        
        return evidence if evidence else None

    def update_individuals_with_phenotypes(self, individuals: List[Dict], 
                                         phenotypes: List[PhenotypeRecord],
                                         diseases: List[DiseaseRecord]) -> List[Dict]:
        """Update individual records with phenotype and disease information."""
        # Create mappings
        phenotype_map = {}
        for phenotype in phenotypes:
            if phenotype.individual_id not in phenotype_map:
                phenotype_map[phenotype.individual_id] = []
            phenotype_map[phenotype.individual_id].append(asdict(phenotype))

        disease_map = {}
        for disease in diseases:
            if disease.individual_id not in disease_map:
                disease_map[disease.individual_id] = []
            disease_map[disease.individual_id].append(asdict(disease))

        # Update individuals
        updated_individuals = []
        for individual in individuals:
            individual_id = individual.get('id', individual.get('individual_id'))
            
            # Add phenotypic features
            if individual_id in phenotype_map:
                individual['phenotypic_features'] = phenotype_map[individual_id]
            
            # Add diseases
            if individual_id in disease_map:
                individual['diseases'] = disease_map[individual_id]
            
            updated_individuals.append(individual)

        return updated_individuals

    def transform_phenotype_file(self, file_path: str, output_dir: str, 
                               individuals_file: str = None) -> Dict:
        """Transform phenotype file to Beacon v2 format."""
        self.logger.info(f"Starting phenotype transformation: {file_path}")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load and normalize data
        df = self.load_phenotype_data(file_path)
        df = self.normalize_phenotype_data(df)
        
        # Transform phenotypes and diseases
        phenotypes = self.transform_phenotypes(df)
        diseases = self.transform_diseases(df)
        
        # Convert to dictionaries
        phenotype_dicts = [asdict(p) for p in phenotypes]
        disease_dicts = [asdict(d) for d in diseases]
        
        # Update individuals if provided
        updated_individuals = []
        if individuals_file and os.path.exists(individuals_file):
            with open(individuals_file, 'r') as f:
                individuals = json.load(f)
            updated_individuals = self.update_individuals_with_phenotypes(
                individuals, phenotypes, diseases
            )
            self._write_json_file(updated_individuals, output_path / "individuals_with_phenotypes.json")

        # Write output files
        self._write_json_file(phenotype_dicts, output_path / "phenotypes.json")
        self._write_json_file(disease_dicts, output_path / "diseases.json")
        
        # Get unique individuals
        unique_individuals = list(set([p.individual_id for p in phenotypes] + 
                                    [d.individual_id for d in diseases]))
        self.stats['individuals_processed'] = len(unique_individuals)
        
        # Generate summary
        summary = {
            'transformation_date': datetime.now().isoformat(),
            'input_file': str(file_path),
            'output_directory': str(output_path),
            'statistics': self.stats,
            'files_created': [
                'phenotypes.json',
                'diseases.json'
            ]
        }
        
        if updated_individuals:
            summary['files_created'].append('individuals_with_phenotypes.json')
        
        self._write_json_file(summary, output_path / "phenotype_transformation_summary.json")
        
        self.logger.info(f"Phenotype transformation completed. Output written to: {output_path}")
        return summary

    def _write_json_file(self, data: any, file_path: Path):
        """Write data to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Transform phenotype data to Beacon v2 format"
    )
    
    parser.add_argument(
        'phenotype_file',
        help='Path to input phenotype file (CSV/TSV/XLSX/JSON)'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output directory for transformed data'
    )
    
    parser.add_argument(
        '-i', '--individuals',
        help='Path to individuals JSON file to update'
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
    transformer = PhenotypeTransformer(args.config)
    
    try:
        # Transform phenotype data
        summary = transformer.transform_phenotype_file(
            file_path=args.phenotype_file,
            output_dir=args.output,
            individuals_file=args.individuals
        )
        
        print("Phenotype transformation completed successfully!")
        print(f"Statistics: {summary['statistics']}")
        print(f"Output files: {summary['files_created']}")
        
    except Exception as e:
        print(f"Error during transformation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 