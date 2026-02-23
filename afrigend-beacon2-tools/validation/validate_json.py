#!/usr/bin/env python3
"""
JSON Validation Tool for AfriGend Beacon v2
Validates JSON data against schemas and Beacon v2 compliance requirements.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass

import yaml
from jsonschema import validate, ValidationError, Draft7Validator
from jsonschema.exceptions import SchemaError

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


@dataclass
class ValidationResult:
    """Data class for validation results."""
    file_path: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    record_count: int
    validation_time: float


class BeaconValidator:
    """Main class for validating Beacon v2 data."""
    
    def __init__(self, config_path: str = None):
        """Initialize the validator."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.schemas = {}
        self.stats = {
            'files_validated': 0,
            'files_passed': 0,
            'files_failed': 0,
            'total_errors': 0,
            'total_warnings': 0
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
            'validation': {
                'strict_mode': False,
                'required_fields_check': True,
                'type_validation': True,
                'range_validation': True
            },
            'processing': {
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

    def get_beacon_v2_schemas(self) -> Dict[str, Dict]:
        """Get built-in Beacon v2 schemas."""
        schemas = {
            'variant': {
                "type": "object",
                "required": ["id", "assembly_id", "reference_name", "start", "end", 
                           "reference_bases", "alternate_bases"],
                "properties": {
                    "id": {"type": "string"},
                    "assembly_id": {"type": "string"},
                    "reference_name": {"type": "string"},
                    "start": {"type": "integer", "minimum": 0},
                    "end": {"type": "integer", "minimum": 0},
                    "reference_bases": {"type": "string"},
                    "alternate_bases": {"type": "string"},
                    "variant_type": {"type": "string"},
                    "annotations": {"type": "array"},
                    "created": {"type": "string", "format": "date-time"},
                    "updated": {"type": "string", "format": "date-time"}
                }
            },
            'individual': {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string"},
                    "sex": {"type": "string", "enum": ["MALE", "FEMALE", "OTHER", "UNKNOWN"]},
                    "ethnicity": {"type": "string"},
                    "geographic_origin": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0},
                    "diseases": {"type": "object"},
                    "phenotypic_features": {"type": "object"},
                    "created": {"type": "string", "format": "date-time"},
                    "updated": {"type": "string", "format": "date-time"}
                }
            },
            'phenotype': {
                "type": "object",
                "required": ["individual_id", "phenotype_id", "phenotype_label", "ontology"],
                "properties": {
                    "individual_id": {"type": "string"},
                    "phenotype_id": {"type": "string"},
                    "phenotype_label": {"type": "string"},
                    "ontology": {"type": "string"},
                    "observed": {"type": "boolean"},
                    "age_of_onset": {"type": "string"},
                    "severity": {"type": "string"},
                    "modifiers": {"type": "array"},
                    "evidence": {"type": "object"},
                    "created": {"type": "string", "format": "date-time"},
                    "updated": {"type": "string", "format": "date-time"}
                }
            },
            'dataset': {
                "type": "object",
                "required": ["id", "name", "description"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "assembly_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "dataset_size": {"type": "object"},
                    "contact_info": {"type": "object"},
                    "created": {"type": "string", "format": "date-time"},
                    "updated": {"type": "string", "format": "date-time"}
                }
            }
        }
        return schemas

    def validate_json_file(self, json_file: str, schema: Dict = None, 
                          schema_type: str = None) -> ValidationResult:
        """Validate a JSON file against a schema."""
        import time
        start_time = time.time()
        
        errors = []
        warnings = []
        
        try:
            # Load JSON data
            data = self._load_json_file(json_file)
            if not data:
                return ValidationResult(
                    file_path=json_file,
                    is_valid=False,
                    errors=["Failed to load JSON data"],
                    warnings=[],
                    record_count=0,
                    validation_time=time.time() - start_time
                )
            
            # Get schema
            if schema is None:
                if schema_type:
                    schemas = self.get_beacon_v2_schemas()
                    schema = schemas.get(schema_type)
                    if not schema:
                        errors.append(f"Unknown schema type: {schema_type}")
                        return ValidationResult(
                            file_path=json_file,
                            is_valid=False,
                            errors=errors,
                            warnings=warnings,
                            record_count=len(data),
                            validation_time=time.time() - start_time
                        )
                else:
                    # Try to infer schema type from filename
                    schema_type = self._infer_schema_type(json_file)
                    if schema_type:
                        schemas = self.get_beacon_v2_schemas()
                        schema = schemas.get(schema_type)
            
            if not schema:
                warnings.append("No schema provided for validation")
                return ValidationResult(
                    file_path=json_file,
                    is_valid=True,
                    errors=errors,
                    warnings=warnings,
                    record_count=len(data),
                    validation_time=time.time() - start_time
                )
            
            # Validate each record
            for i, record in enumerate(data):
                try:
                    validate(instance=record, schema=schema)
                except ValidationError as e:
                    error_msg = f"Record {i+1}: {e.message}"
                    if e.path:
                        error_msg += f" at {'/'.join(str(p) for p in e.path)}"
                    errors.append(error_msg)
                    
                    # Stop on first error in strict mode
                    if self.config['validation']['strict_mode']:
                        break
            
            is_valid = len(errors) == 0
            
            return ValidationResult(
                file_path=json_file,
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                record_count=len(data),
                validation_time=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Error validating {json_file}: {e}")
            return ValidationResult(
                file_path=json_file,
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings,
                record_count=0,
                validation_time=time.time() - start_time
            )

    def _load_json_file(self, json_file: str) -> List[Dict]:
        """Load data from JSON file."""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                self.logger.error(f"Invalid JSON format in {json_file}")
                return []
                
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {json_file}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error loading {json_file}: {e}")
            return []

    def _infer_schema_type(self, file_path: str) -> Optional[str]:
        """Infer schema type from filename."""
        filename = Path(file_path).name.lower()
        
        if 'variant' in filename:
            return 'variant'
        elif 'individual' in filename:
            return 'individual'
        elif 'phenotype' in filename:
            return 'phenotype'
        elif 'dataset' in filename:
            return 'dataset'
        elif 'disease' in filename:
            return 'phenotype'  # Use phenotype schema for diseases
        elif 'biosample' in filename:
            return 'individual'  # Use individual schema for biosamples
        elif 'analysis' in filename:
            return 'individual'  # Use individual schema for analyses
        elif 'cohort' in filename:
            return 'individual'  # Use individual schema for cohorts
        
        return None

    def validate_directory(self, input_dir: str, schema_type: str = None) -> List[ValidationResult]:
        """Validate all JSON files in a directory."""
        results = []
        input_path = Path(input_dir)
        
        if not input_path.exists():
            self.logger.error(f"Directory not found: {input_dir}")
            return results
        
        # Find all JSON files
        json_files = list(input_path.glob('*.json')) + list(input_path.glob('*.jsonl'))
        
        for json_file in json_files:
            self.logger.info(f"Validating {json_file}")
            result = self.validate_json_file(str(json_file), schema_type=schema_type)
            results.append(result)
            
            # Update statistics
            self.stats['files_validated'] += 1
            if result.is_valid:
                self.stats['files_passed'] += 1
            else:
                self.stats['files_failed'] += 1
            
            self.stats['total_errors'] += len(result.errors)
            self.stats['total_warnings'] += len(result.warnings)
        
        return results


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Validate JSON data for AfriGend Beacon v2 compliance"
    )
    
    parser.add_argument(
        'input',
        help='Input JSON file or directory'
    )
    
    parser.add_argument(
        '--schema-type',
        choices=['variant', 'individual', 'phenotype', 'dataset'],
        help='Use built-in Beacon v2 schema type'
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Stop validation on first error'
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
    
    # Initialize validator
    validator = BeaconValidator(args.config)
    
    # Set strict mode
    if args.strict:
        validator.config['validation']['strict_mode'] = True
    
    try:
        # Validate data
        if os.path.isfile(args.input):
            # Validate single file
            result = validator.validate_json_file(args.input, schema_type=args.schema_type)
            results = [result]
            
        elif os.path.isdir(args.input):
            # Validate directory
            results = validator.validate_directory(args.input, args.schema_type)
            
        else:
            print(f"Error: {args.input} is not a valid file or directory")
            sys.exit(1)
        
        # Print results
        print("\nValidation Results:")
        print("=" * 50)
        
        for result in results:
            status = "PASS" if result.is_valid else "FAIL"
            print(f"\n{result.file_path}: {status}")
            print(f"  Records: {result.record_count}")
            print(f"  Validation time: {result.validation_time:.2f}s")
            
            if result.errors:
                print(f"  Errors ({len(result.errors)}):")
                for error in result.errors[:5]:  # Show first 5 errors
                    print(f"    - {error}")
                if len(result.errors) > 5:
                    print(f"    ... and {len(result.errors) - 5} more errors")
            
            if result.warnings:
                print(f"  Warnings ({len(result.warnings)}):")
                for warning in result.warnings[:3]:  # Show first 3 warnings
                    print(f"    - {warning}")
                if len(result.warnings) > 3:
                    print(f"    ... and {len(result.warnings) - 3} more warnings")
        
        # Print summary
        print("\n" + "=" * 50)
        print("Summary:")
        print(f"  Files validated: {validator.stats['files_validated']}")
        print(f"  Files passed: {validator.stats['files_passed']}")
        print(f"  Files failed: {validator.stats['files_failed']}")
        print(f"  Total errors: {validator.stats['total_errors']}")
        print(f"  Total warnings: {validator.stats['total_warnings']}")
        
        # Exit with error code if any files failed
        if validator.stats['files_failed'] > 0:
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
