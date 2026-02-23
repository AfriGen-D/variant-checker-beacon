#!/usr/bin/env python3
"""
Data Import Tool for AfriGend Beacon v2
Imports JSON data into MongoDB collections with validation and progress tracking.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from tqdm import tqdm

import yaml
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, ConnectionFailure

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


class MongoImporter:
    """Main class for importing data into MongoDB."""
    
    def __init__(self, config_path: str = None):
        """Initialize the MongoDB importer."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.client = None
        self.stats = {
            'files_processed': 0,
            'records_imported': 0,
            'errors': 0,
            'collections_created': 0
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
            'mongodb': {
                'host': 'localhost',
                'port': 27017,
                'database': 'beacon_db',
                'connection_timeout': 30
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

    def connect_to_mongodb(self, mongo_uri: str = None) -> bool:
        """Connect to MongoDB database."""
        try:
            if mongo_uri:
                self.client = MongoClient(mongo_uri)
            else:
                mongo_config = self.config['mongodb']
                mongo_uri = f"mongodb://{mongo_config['host']}:{mongo_config['port']}/"
                self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=mongo_config['connection_timeout'] * 1000)
            
            # Test connection
            self.client.admin.command('ping')
            self.logger.info("Successfully connected to MongoDB")
            return True
            
        except ConnectionFailure as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False

    def import_json_file(self, json_file: str, db_name: str, collection_name: str, 
                        batch_size: int = None) -> bool:
        """Import JSON file into MongoDB collection."""
        if not self.client:
            self.logger.error("Not connected to MongoDB")
            return False

        batch_size = batch_size or self.config['processing']['batch_size']
        show_progress = self.config['processing']['show_progress']
        
        try:
            db = self.client[db_name]
            collection = db[collection_name]
            
            # Check if file exists
            if not os.path.exists(json_file):
                self.logger.error(f"File not found: {json_file}")
                return False

            # Determine file type and load data
            if json_file.endswith('.jsonl'):
                data = self._load_jsonl_file(json_file)
            else:
                data = self._load_json_file(json_file)

            if not data:
                self.logger.warning(f"No data found in {json_file}")
                return False

            # Import data in batches
            total_records = len(data)
            self.logger.info(f"Importing {total_records} records to {db_name}.{collection_name}")
            
            with tqdm(total=total_records, desc=f"Importing {collection_name}", 
                     disable=not show_progress) as pbar:
                
                for i in range(0, total_records, batch_size):
                    batch = data[i:i + batch_size]
                    
                    # Remove MongoDB _id if present to avoid conflicts
                    for record in batch:
                        if isinstance(record, dict):
                            record.pop('_id', None)
                    
                    try:
                        if len(batch) == 1:
                            result = collection.insert_one(batch[0])
                        else:
                            result = collection.insert_many(batch, ordered=False)
                        
                        self.stats['records_imported'] += len(batch)
                        pbar.update(len(batch))
                        
                    except BulkWriteError as e:
                        self.logger.warning(f"Some records failed to import: {e.details}")
                        # Count successful inserts
                        successful = len(e.details.get('writeErrors', []))
                        self.stats['records_imported'] += (len(batch) - successful)
                        self.stats['errors'] += successful
                        pbar.update(len(batch))
                        
                    except Exception as e:
                        self.logger.error(f"Error importing batch: {e}")
                        self.stats['errors'] += len(batch)
                        pbar.update(len(batch))

            self.stats['files_processed'] += 1
            self.logger.info(f"Successfully imported {self.stats['records_imported']} records to {collection_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing {json_file}: {e}")
            self.stats['errors'] += 1
            return False

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

    def _load_jsonl_file(self, jsonl_file: str) -> List[Dict]:
        """Load data from JSONL file (one JSON object per line)."""
        data = []
        try:
            with open(jsonl_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            data.append(record)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Invalid JSON on line {line_num}: {e}")
                            continue
            return data
            
        except Exception as e:
            self.logger.error(f"Error loading {jsonl_file}: {e}")
            return []

    def import_directory(self, input_dir: str, db_name: str, 
                        collection_mapping: Dict[str, str] = None) -> Dict:
        """Import all JSON files from a directory."""
        if not self.client:
            self.logger.error("Not connected to MongoDB")
            return {}

        if collection_mapping is None:
            # Default mapping based on filename
            collection_mapping = {
                'variants': 'variants',
                'individuals': 'individuals',
                'phenotypes': 'phenotypes',
                'diseases': 'diseases',
                'biosamples': 'biosamples',
                'analyses': 'analyses',
                'cohorts': 'cohorts'
            }

        results = {}
        input_path = Path(input_dir)
        
        if not input_path.exists():
            self.logger.error(f"Directory not found: {input_dir}")
            return results

        # Find all JSON files
        json_files = list(input_path.glob('*.json')) + list(input_path.glob('*.jsonl'))
        
        for json_file in json_files:
            # Determine collection name
            collection_name = None
            for key, value in collection_mapping.items():
                if key in json_file.name.lower():
                    collection_name = value
                    break
            
            if not collection_name:
                # Use filename without extension as collection name
                collection_name = json_file.stem

            self.logger.info(f"Importing {json_file} to collection {collection_name}")
            
            success = self.import_json_file(str(json_file), db_name, collection_name)
            results[str(json_file)] = {
                'success': success,
                'collection': collection_name,
                'records_imported': self.stats['records_imported']
            }

        return results

    def close_connection(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Import JSON data into MongoDB for AfriGend Beacon v2"
    )
    
    parser.add_argument(
        'input',
        help='Input JSON file or directory'
    )
    
    parser.add_argument(
        '--db',
        required=True,
        help='MongoDB database name'
    )
    
    parser.add_argument(
        '--collection',
        help='MongoDB collection name (required for single file import)'
    )
    
    parser.add_argument(
        '--mongo-uri',
        help='MongoDB connection URI (overrides config file)'
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Batch size for bulk operations'
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
    
    # Initialize importer
    importer = MongoImporter(args.config)
    
    try:
        # Connect to MongoDB
        if not importer.connect_to_mongodb(args.mongo_uri):
            sys.exit(1)
        
        # Import data
        if os.path.isfile(args.input):
            if not args.collection:
                print("Error: --collection is required for single file import")
                sys.exit(1)
            
            success = importer.import_json_file(
                args.input, 
                args.db, 
                args.collection,
                args.batch_size
            )
            
            if success:
                print(f"Successfully imported {args.input} to {args.db}.{args.collection}")
            else:
                print(f"Failed to import {args.input}")
                sys.exit(1)
                
        elif os.path.isdir(args.input):
            results = importer.import_directory(args.input, args.db)
            
            print("\nImport Summary:")
            for file_path, result in results.items():
                status = "SUCCESS" if result['success'] else "FAILED"
                print(f"  {file_path} -> {result['collection']}: {status}")
                
        else:
            print(f"Error: {args.input} is not a valid file or directory")
            sys.exit(1)
            
        # Print statistics
        print(f"\nStatistics:")
        print(f"  Files processed: {importer.stats['files_processed']}")
        print(f"  Records imported: {importer.stats['records_imported']}")
        print(f"  Errors: {importer.stats['errors']}")
        
    except KeyboardInterrupt:
        print("\nImport interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during import: {e}")
        sys.exit(1)
    finally:
        importer.close_connection()


if __name__ == "__main__":
    main() 