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
from typing import Dict, Iterator, List, Optional, Union
from tqdm import tqdm

import yaml
from pymongo import MongoClient, InsertOne, ReplaceOne
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

            # Determine file type and stream data. JSONL is streamed record by
            # record — a chromosome-scale variants file does not fit in memory.
            if json_file.endswith('.jsonl'):
                records = self._iter_jsonl_file(json_file)
            else:
                records = iter(self._load_json_file(json_file))

            self.logger.info(f"Importing records to {db_name}.{collection_name}")

            batch = []
            seen = 0
            failed = False

            with tqdm(desc=f"Importing {collection_name}", disable=not show_progress) as pbar:
                for record in records:
                    batch.append(record)
                    seen += 1
                    if len(batch) >= batch_size:
                        failed |= not self._write_batch(collection, batch)
                        pbar.update(len(batch))
                        batch = []

                if batch:
                    failed |= not self._write_batch(collection, batch)
                    pbar.update(len(batch))

            if seen == 0:
                self.logger.warning(f"No data found in {json_file}")
                return False

            self.stats['files_processed'] += 1
            self.logger.info(f"Imported {self.stats['records_imported']} records to {collection_name}")
            return not failed

        except Exception as e:
            self.logger.error(f"Error importing {json_file}: {e}")
            self.stats['errors'] += 1
            return False

    @staticmethod
    def _natural_key(record: Dict) -> Optional[Union[str, int]]:
        """Return the record's natural key, or None if it has none.

        Variants and individuals carry it as `id` (CHROM:POS:REF:ALT, sample
        ID). Phenotype and disease records have no `id` — their natural key is
        the individual plus the term.
        """
        key = record.get('id')
        if isinstance(key, (str, int)) and key != '':
            return key

        individual_id = record.get('individual_id')
        for term_field in ('phenotype_id', 'disease_id'):
            if individual_id and record.get(term_field):
                return f"{individual_id}:{record[term_field]}"

        return None

    def _write_batch(self, collection, batch: List[Dict]) -> bool:
        """Upsert a batch of records. Returns False if any record failed.

        Records are keyed on the natural key the transform already computes
        (`id` — CHROM:POS:REF:ALT for variants, the sample ID for individuals),
        written to `_id` so that re-running the pipeline replaces documents
        instead of duplicating them. One bulk round trip per batch.
        """
        operations = []
        for record in batch:
            if not isinstance(record, dict):
                self.logger.warning(f"Skipping non-object record: {record!r}")
                self.stats['errors'] += 1
                continue

            record.pop('_id', None)
            natural_key = self._natural_key(record)
            if natural_key is not None:
                record['_id'] = natural_key
                operations.append(ReplaceOne({'_id': natural_key}, record, upsert=True))
            else:
                # Nothing to key on — insert, and say so rather than silently
                # pretending the import was idempotent.
                self.logger.warning("Record has no 'id' field; inserting without upsert key")
                operations.append(InsertOne(record))

        if not operations:
            return False

        try:
            collection.bulk_write(operations, ordered=False)
            self.stats['records_imported'] += len(operations)
            return True

        except BulkWriteError as e:
            write_errors = e.details.get('writeErrors', []) if e.details else []
            failed_count = len(write_errors) or len(operations)
            self.logger.error(f"{failed_count} records failed to import: {e.details}")
            self.stats['records_imported'] += (len(operations) - failed_count)
            self.stats['errors'] += failed_count
            return False

        except Exception as e:
            self.logger.error(f"Error importing batch: {e}")
            self.stats['errors'] += len(operations)
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

    def _iter_jsonl_file(self, jsonl_file: str) -> Iterator[Dict]:
        """Yield records from a JSONL file (one JSON object per line).

        Streams — the variants file for a single chromosome is millions of
        records and must never be materialized as a list.
        """
        with open(jsonl_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Invalid JSON on line {line_num}: {e}")

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

            if not results or not all(r['success'] for r in results.values()):
                print("Import failed for at least one file")
                sys.exit(1)

        else:
            print(f"Error: {args.input} is not a valid file or directory")
            sys.exit(1)

        # Print statistics
        print(f"\nStatistics:")
        print(f"  Files processed: {importer.stats['files_processed']}")
        print(f"  Records imported: {importer.stats['records_imported']}")
        print(f"  Errors: {importer.stats['errors']}")

        # A failed batch must stop the pipeline, not be swallowed into a stat
        if importer.stats['errors'] > 0:
            print(f"Import completed with {importer.stats['errors']} failed records")
            sys.exit(1)

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