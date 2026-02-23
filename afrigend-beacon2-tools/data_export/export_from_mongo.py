#!/usr/bin/env python3
"""
Data Export Tool for AfriGend Beacon v2
Exports data from MongoDB collections to JSON files with filtering and formatting.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from tqdm import tqdm

import yaml
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId, json_util

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


class MongoExporter:
    """Main class for exporting data from MongoDB."""
    
    def __init__(self, config_path: str = None):
        """Initialize the MongoDB exporter."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.client = None
        self.stats = {
            'collections_exported': 0,
            'records_exported': 0,
            'files_created': 0,
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
            'mongodb': {
                'host': 'localhost',
                'port': 27017,
                'database': 'beacon_db',
                'connection_timeout': 30
            },
            'processing': {
                'batch_size': 1000,
                'show_progress': True
            },
            'output': {
                'pretty_json': True,
                'include_metadata': True
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

    def export_collection(self, db_name: str, collection_name: str, output_file: str,
                         query: Dict = None, projection: Dict = None, 
                         sort: List = None, limit: int = None) -> bool:
        """Export a single collection to JSON file."""
        if not self.client:
            self.logger.error("Not connected to MongoDB")
            return False

        try:
            db = self.client[db_name]
            collection = db[collection_name]
            
            # Build query
            if query is None:
                query = {}
            
            # Count total documents
            total_docs = collection.count_documents(query)
            if total_docs == 0:
                self.logger.warning(f"No documents found in {db_name}.{collection_name}")
                return True
            
            self.logger.info(f"Exporting {total_docs} documents from {db_name}.{collection_name}")
            
            # Execute query
            cursor = collection.find(query, projection)
            if sort:
                cursor = cursor.sort(sort)
            if limit:
                cursor = cursor.limit(limit)
            
            # Export data
            data = []
            show_progress = self.config['processing']['show_progress']
            
            with tqdm(total=total_docs, desc=f"Exporting {collection_name}", 
                     disable=not show_progress) as pbar:
                
                for doc in cursor:
                    # Convert ObjectId to string for JSON serialization
                    doc = self._prepare_document_for_export(doc)
                    data.append(doc)
                    pbar.update(1)
            
            # Write to file
            success = self._write_json_file(data, output_file)
            
            if success:
                self.stats['records_exported'] += len(data)
                self.stats['files_created'] += 1
                self.stats['collections_exported'] += 1
                self.logger.info(f"Successfully exported {len(data)} records to {output_file}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error exporting {db_name}.{collection_name}: {e}")
            self.stats['errors'] += 1
            return False

    def export_database(self, db_name: str, output_dir: str, 
                       collections: List[str] = None, 
                       exclude_collections: List[str] = None) -> Dict:
        """Export entire database or specific collections."""
        if not self.client:
            self.logger.error("Not connected to MongoDB")
            return {}

        try:
            db = self.client[db_name]
            
            # Get list of collections
            if collections:
                collection_names = collections
            else:
                collection_names = db.list_collection_names()
            
            # Filter out excluded collections
            if exclude_collections:
                collection_names = [c for c in collection_names if c not in exclude_collections]
            
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            results = {}
            
            for collection_name in collection_names:
                output_file = output_path / f"{collection_name}.json"
                
                self.logger.info(f"Exporting collection: {collection_name}")
                
                success = self.export_collection(db_name, collection_name, str(output_file))
                
                results[collection_name] = {
                    'success': success,
                    'output_file': str(output_file),
                    'records_exported': self.stats['records_exported']
                }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error exporting database {db_name}: {e}")
            return {}

    def export_with_aggregation(self, db_name: str, collection_name: str, 
                               pipeline: List[Dict], output_file: str) -> bool:
        """Export data using MongoDB aggregation pipeline."""
        if not self.client:
            self.logger.error("Not connected to MongoDB")
            return False

        try:
            db = self.client[db_name]
            collection = db[collection_name]
            
            self.logger.info(f"Running aggregation on {db_name}.{collection_name}")
            
            # Execute aggregation
            cursor = collection.aggregate(pipeline)
            
            # Export results
            data = []
            for doc in cursor:
                doc = self._prepare_document_for_export(doc)
                data.append(doc)
            
            # Write to file
            success = self._write_json_file(data, output_file)
            
            if success:
                self.stats['records_exported'] += len(data)
                self.stats['files_created'] += 1
                self.logger.info(f"Successfully exported {len(data)} aggregated records to {output_file}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error in aggregation export: {e}")
            self.stats['errors'] += 1
            return False

    def _prepare_document_for_export(self, doc: Dict) -> Dict:
        """Prepare document for JSON export by handling MongoDB-specific types."""
        # Convert ObjectId to string
        if '_id' in doc and isinstance(doc['_id'], ObjectId):
            doc['_id'] = str(doc['_id'])
        
        # Handle other MongoDB types if needed
        # This is a simplified version - you might want to use json_util.dumps() for more complex cases
        return doc

    def _write_json_file(self, data: List[Dict], output_file: str) -> bool:
        """Write data to JSON file."""
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            pretty_json = self.config['output']['pretty_json']
            include_metadata = self.config['output']['include_metadata']
            
            if include_metadata:
                export_data = {
                    'metadata': {
                        'export_date': datetime.now().isoformat(),
                        'record_count': len(data),
                        'source': 'mongodb_export'
                    },
                    'data': data
                }
            else:
                export_data = data
            
            with open(output_path, 'w') as f:
                if pretty_json:
                    json.dump(export_data, f, indent=2, default=str)
                else:
                    json.dump(export_data, f, default=str)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing to {output_file}: {e}")
            return False

    def close_connection(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Export data from MongoDB for AfriGend Beacon v2"
    )
    
    parser.add_argument(
        '--db',
        required=True,
        help='MongoDB database name'
    )
    
    parser.add_argument(
        '--collection',
        help='MongoDB collection name (for single collection export)'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Output file or directory'
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
        '--query',
        help='MongoDB query filter (JSON string)'
    )
    
    parser.add_argument(
        '--projection',
        help='MongoDB projection (JSON string)'
    )
    
    parser.add_argument(
        '--sort',
        help='Sort criteria (JSON string)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of documents to export'
    )
    
    parser.add_argument(
        '--collections',
        nargs='+',
        help='Specific collections to export (for database export)'
    )
    
    parser.add_argument(
        '--exclude',
        nargs='+',
        help='Collections to exclude (for database export)'
    )
    
    parser.add_argument(
        '--aggregation',
        help='Aggregation pipeline file (JSON)'
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
    
    # Initialize exporter
    exporter = MongoExporter(args.config)
    
    try:
        # Connect to MongoDB
        if not exporter.connect_to_mongodb(args.mongo_uri):
            sys.exit(1)
        
        # Parse query parameters
        query = json.loads(args.query) if args.query else None
        projection = json.loads(args.projection) if args.projection else None
        sort = json.loads(args.sort) if args.sort else None
        
        # Export data
        if args.aggregation:
            # Export using aggregation pipeline
            with open(args.aggregation, 'r') as f:
                pipeline = json.load(f)
            
            if not args.collection:
                print("Error: --collection is required for aggregation export")
                sys.exit(1)
            
            success = exporter.export_with_aggregation(
                args.db, args.collection, pipeline, args.output
            )
            
            if not success:
                sys.exit(1)
                
        elif args.collection:
            # Export single collection
            success = exporter.export_collection(
                args.db, args.collection, args.output,
                query, projection, sort, args.limit
            )
            
            if not success:
                sys.exit(1)
                
        else:
            # Export entire database
            results = exporter.export_database(
                args.db, args.output, args.collections, args.exclude
            )
            
            print("\nExport Summary:")
            for collection_name, result in results.items():
                status = "SUCCESS" if result['success'] else "FAILED"
                print(f"  {collection_name}: {status} -> {result['output_file']}")
        
        # Print statistics
        print(f"\nStatistics:")
        print(f"  Collections exported: {exporter.stats['collections_exported']}")
        print(f"  Records exported: {exporter.stats['records_exported']}")
        print(f"  Files created: {exporter.stats['files_created']}")
        print(f"  Errors: {exporter.stats['errors']}")
        
    except KeyboardInterrupt:
        print("\nExport interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during export: {e}")
        sys.exit(1)
    finally:
        exporter.close_connection()


if __name__ == "__main__":
    main() 