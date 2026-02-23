#!/usr/bin/env python3
"""
Basic tests for AfriGend Beacon v2 Tools
Tests that all tools can be imported and have the expected structure.
"""

import sys
import os
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class TestToolsImport(unittest.TestCase):
    """Test that all tools can be imported correctly."""
    
    def test_vcf_transform_import(self):
        """Test VCF transformation tool import."""
        try:
            from vcf_transform.vcf_to_beacon import VCFTransformer
            self.assertTrue(hasattr(VCFTransformer, '__init__'))
            self.assertTrue(hasattr(VCFTransformer, 'transform_vcf_to_beacon'))
        except ImportError as e:
            self.fail(f"Failed to import VCFTransformer: {e}")
    
    def test_phenotype_transform_import(self):
        """Test phenotype transformation tool import."""
        try:
            from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer
            self.assertTrue(hasattr(PhenotypeTransformer, '__init__'))
            self.assertTrue(hasattr(PhenotypeTransformer, 'transform_phenotype_file'))
        except ImportError as e:
            self.fail(f"Failed to import PhenotypeTransformer: {e}")
    
    def test_validation_import(self):
        """Test validation tool import."""
        try:
            from validation.validate_json import BeaconValidator
            self.assertTrue(hasattr(BeaconValidator, '__init__'))
            self.assertTrue(hasattr(BeaconValidator, 'validate_json_file'))
        except ImportError as e:
            self.fail(f"Failed to import BeaconValidator: {e}")
    
    def test_import_tool_import(self):
        """Test import tool import."""
        try:
            from data_import.import_to_mongo import MongoImporter
            self.assertTrue(hasattr(MongoImporter, '__init__'))
            self.assertTrue(hasattr(MongoImporter, 'import_json_file'))
        except ImportError as e:
            self.fail(f"Failed to import MongoImporter: {e}")
    
    def test_export_tool_import(self):
        """Test export tool import."""
        try:
            from data_export.export_from_mongo import MongoExporter
            self.assertTrue(hasattr(MongoExporter, '__init__'))
            self.assertTrue(hasattr(MongoExporter, 'export_collection'))
        except ImportError as e:
            self.fail(f"Failed to import MongoExporter: {e}")


class TestConfiguration(unittest.TestCase):
    """Test configuration loading."""
    
    def test_config_file_exists(self):
        """Test that configuration file exists."""
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        self.assertTrue(config_path.exists(), f"Config file not found: {config_path}")
    
    def test_config_loading(self):
        """Test that configuration can be loaded."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check required sections
            self.assertIn('mongodb', config)
            self.assertIn('vcf', config)
            self.assertIn('phenotypes', config)
            self.assertIn('validation', config)
            self.assertIn('processing', config)
            
        except Exception as e:
            self.fail(f"Failed to load configuration: {e}")


class TestSchemas(unittest.TestCase):
    """Test Beacon v2 schemas."""
    
    def test_beacon_schemas(self):
        """Test that Beacon v2 schemas are available."""
        try:
            from validation.validate_json import BeaconValidator
            validator = BeaconValidator()
            schemas = validator.get_beacon_v2_schemas()
            
            # Check that all expected schemas are present
            expected_schemas = ['variant', 'individual', 'phenotype', 'dataset']
            for schema_name in expected_schemas:
                self.assertIn(schema_name, schemas)
                self.assertIsInstance(schemas[schema_name], dict)
                
        except Exception as e:
            self.fail(f"Failed to get Beacon schemas: {e}")


class TestRequirements(unittest.TestCase):
    """Test that required packages are available."""
    
    def test_required_packages(self):
        """Test that required packages can be imported."""
        required_packages = [
            'yaml',
            'pandas',
            'numpy',
            'tqdm',
            'pymongo',
            'jsonschema',
            'cyvcf2',
            'pronto'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError as e:
                self.fail(f"Required package {package} not available: {e}")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2) 