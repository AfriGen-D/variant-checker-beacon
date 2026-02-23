# API Reference

## Table of Contents

1. [VCF Transformation API](#vcf-transformation-api)
2. [Phenotype Transformation API](#phenotype-transformation-api)
3. [Validation API](#validation-api)
4. [Data Import API](#data-import-api)
5. [Data Export API](#data-export-api)
6. [Configuration API](#configuration-api)
7. [Utility Functions](#utility-functions)

## VCF Transformation API

### vcf_to_beacon.py

**Location**: `vcf_transform/vcf_to_beacon.py`

#### Command Line Interface

```bash
python vcf_transform/vcf_to_beacon.py [OPTIONS] INPUT_VCF
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | PATH | `./output` | Output directory |
| `--assembly` | TEXT | `GRCh38` | Genome assembly |
| `--metadata` | PATH | - | Individual metadata file |
| `--config` | PATH | `config/settings.yaml` | Configuration file |
| `--min-qual` | FLOAT | `20.0` | Minimum variant quality |
| `--min-depth` | INT | `10` | Minimum read depth |
| `--max-missing` | FLOAT | `0.1` | Maximum missing rate |
| `--batch-size` | INT | `1000` | Processing batch size |
| `--include-annotations` | FLAG | - | Include VCF annotations |
| `--annotation-type` | CHOICE | `VEP` | Annotation type (VEP/SnpEff) |
| `--verbose`, `-v` | FLAG | - | Verbose output |
| `--help` | FLAG | - | Show help message |

#### Python API

```python
from vcf_transform.vcf_to_beacon import VCFTransformer

# Initialize transformer
transformer = VCFTransformer(
    config_path="config/settings.yaml",
    assembly="GRCh38",
    min_qual=20.0,
    min_depth=10,
    max_missing_rate=0.1
)

# Transform VCF file
results = transformer.transform_vcf(
    vcf_path="input.vcf",
    output_dir="./output",
    metadata_path="individuals.csv",
    batch_size=1000,
    include_annotations=True
)

# Access results
print(f"Processed {results['total_variants']} variants")
print(f"Output files: {results['output_files']}")
```

#### Class Methods

##### VCFTransformer

```python
class VCFTransformer:
    def __init__(self, config_path=None, assembly="GRCh38", **kwargs):
        """Initialize VCF transformer with configuration."""
        
    def transform_vcf(self, vcf_path, output_dir, **kwargs):
        """Transform VCF file to Beacon v2 format."""
        
    def load_metadata(self, metadata_path):
        """Load individual metadata from CSV/TSV file."""
        
    def process_variant_record(self, vcf_record):
        """Process single VCF record to Beacon v2 format."""
        
    def apply_quality_filters(self, vcf_record):
        """Apply quality filters to VCF record."""
        
    def extract_annotations(self, vcf_record, annotation_type="VEP"):
        """Extract annotations from VCF record."""
        
    def generate_summary_report(self, output_dir):
        """Generate processing summary report."""
```

#### Return Values

The `transform_vcf` method returns a dictionary with:

```python
{
    "total_variants": int,
    "filtered_variants": int,
    "total_individuals": int,
    "output_files": {
        "variants": "path/to/variants_batch.jsonl",
        "individuals": "path/to/individuals.json",
        "genotypes": "path/to/variant_genotypes.json",
        "summary": "path/to/transformation_summary.json"
    },
    "processing_time": float,
    "statistics": {
        "variant_types": dict,
        "quality_distribution": dict,
        "chromosome_counts": dict
    }
}
```

## Phenotype Transformation API

### phenotype_to_beacon.py

**Location**: `phenotype_transform/phenotype_to_beacon.py`

#### Command Line Interface

```bash
python phenotype_transform/phenotype_to_beacon.py [OPTIONS] INPUT_FILE
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | PATH | `./output` | Output directory |
| `--individuals` | PATH | - | Individual records file |
| `--config` | PATH | `config/settings.yaml` | Configuration file |
| `--ontology` | CHOICE | `HPO` | Primary ontology (HPO/MONDO/ORDO) |
| `--ontology-file` | PATH | - | Local ontology file |
| `--auto-map-ontologies` | FLAG | - | Auto-map ontology IDs |
| `--ontology-cache` | PATH | `./cache` | Ontology cache directory |
| `--include-diseases` | FLAG | - | Include disease processing |
| `--batch-size` | INT | `1000` | Processing batch size |
| `--verbose`, `-v` | FLAG | - | Verbose output |

#### Python API

```python
from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer

# Initialize transformer
transformer = PhenotypeTransformer(
    config_path="config/settings.yaml",
    primary_ontology="HPO",
    auto_map_ontologies=True
)

# Transform phenotype data
results = transformer.transform_phenotypes(
    input_path="phenotypes.csv",
    output_dir="./output",
    individuals_path="individuals.json",
    include_diseases=True
)
```

#### Class Methods

##### PhenotypeTransformer

```python
class PhenotypeTransformer:
    def __init__(self, config_path=None, primary_ontology="HPO", **kwargs):
        """Initialize phenotype transformer."""
        
    def transform_phenotypes(self, input_path, output_dir, **kwargs):
        """Transform phenotype data to Beacon v2 format."""
        
    def load_ontology(self, ontology_type, ontology_file=None):
        """Load ontology from file or web service."""
        
    def map_phenotype_id(self, phenotype_id):
        """Map phenotype ID to ontology terms."""
        
    def process_phenotype_record(self, record):
        """Process single phenotype record."""
        
    def extract_disease_info(self, record):
        """Extract disease information from record."""
        
    def validate_ontology_terms(self, terms):
        """Validate ontology terms."""
```

## Validation API

### validate_json.py

**Location**: `validation/validate_json.py`

#### Command Line Interface

```bash
python validation/validate_json.py [OPTIONS] INPUT
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--schema-type` | CHOICE | - | Schema type (variant/individual/phenotype/dataset) |
| `--config` | PATH | `config/settings.yaml` | Configuration file |
| `--strict` | FLAG | - | Strict validation mode |
| `--lenient` | FLAG | - | Lenient validation mode |
| `--verbose`, `-v` | FLAG | - | Verbose output |

#### Python API

```python
from validation.validate_json import BeaconValidator

# Initialize validator
validator = BeaconValidator(config_path="config/settings.yaml")

# Validate single file
result = validator.validate_json_file(
    file_path="variants.json",
    schema_type="variant"
)

# Validate directory
results = validator.validate_directory(
    input_dir="./output",
    schema_type="variant"
)
```

#### Class Methods

##### BeaconValidator

```python
class BeaconValidator:
    def __init__(self, config_path=None):
        """Initialize Beacon v2 validator."""
        
    def validate_json_file(self, file_path, schema_type=None):
        """Validate single JSON file."""
        
    def validate_directory(self, input_dir, schema_type=None):
        """Validate all JSON files in directory."""
        
    def get_beacon_v2_schemas(self):
        """Get built-in Beacon v2 schemas."""
        
    def infer_schema_type(self, file_path):
        """Infer schema type from filename."""
```

#### ValidationResult

```python
class ValidationResult:
    def __init__(self):
        self.file_path = ""
        self.is_valid = False
        self.record_count = 0
        self.errors = []
        self.warnings = []
        self.validation_time = 0.0
        self.schema_type = ""
```

## Data Import API

### import_to_mongo.py

**Location**: `data_import/import_to_mongo.py`

#### Command Line Interface

```bash
python data_import/import_to_mongo.py [OPTIONS] INPUT
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--db` | TEXT | `beacon_db` | Database name |
| `--collection` | TEXT | - | Collection name |
| `--mongo-uri` | TEXT | `mongodb://localhost:27017/` | MongoDB URI |
| `--batch-size` | INT | `1000` | Import batch size |
| `--upsert` | FLAG | - | Enable upsert mode |
| `--create-indexes` | FLAG | - | Create indexes |
| `--validate-before-import` | FLAG | - | Validate before import |
| `--auto-detect-collections` | FLAG | - | Auto-detect collections |
| `--drop-existing` | FLAG | - | Drop existing collections |
| `--verbose`, `-v` | FLAG | - | Verbose output |

#### Python API

```python
from data_import.import_to_mongo import MongoImporter

# Initialize importer
importer = MongoImporter(
    mongo_uri="mongodb://localhost:27017/",
    database="beacon_db",
    batch_size=1000
)

# Import single file
result = importer.import_file(
    file_path="variants.json",
    collection="variants",
    upsert=True
)

# Import directory
results = importer.import_directory(
    input_dir="./output",
    auto_detect_collections=True
)
```

#### Class Methods

##### MongoImporter

```python
class MongoImporter:
    def __init__(self, mongo_uri, database, batch_size=1000):
        """Initialize MongoDB importer."""
        
    def import_file(self, file_path, collection, **kwargs):
        """Import single JSON file to MongoDB."""
        
    def import_directory(self, input_dir, **kwargs):
        """Import all JSON files from directory."""
        
    def create_indexes(self, collection_name, index_specs):
        """Create database indexes."""
        
    def validate_data(self, data, schema_type):
        """Validate data before import."""
```

## Data Export API

### export_from_mongo.py

**Location**: `data_export/export_from_mongo.py`

#### Command Line Interface

```bash
python data_export/export_from_mongo.py [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--db` | TEXT | `beacon_db` | Database name |
| `--collection` | TEXT | - | Collection name |
| `--output` | PATH | - | Output file path |
| `--mongo-uri` | TEXT | `mongodb://localhost:27017/` | MongoDB URI |
| `--query` | TEXT | `{}` | Query filter (JSON) |
| `--projection` | TEXT | - | Field projection (JSON) |
| `--aggregation` | TEXT | - | Aggregation pipeline (JSON) |
| `--format` | CHOICE | `json` | Output format (json/csv/tsv) |
| `--include-metadata` | FLAG | - | Include metadata |
| `--batch-size` | INT | `1000` | Export batch size |
| `--verbose`, `-v` | FLAG | - | Verbose output |

#### Python API

```python
from data_export.export_from_mongo import MongoExporter

# Initialize exporter
exporter = MongoExporter(
    mongo_uri="mongodb://localhost:27017/",
    database="beacon_db"
)

# Export collection
result = exporter.export_collection(
    collection="variants",
    output_path="variants.json",
    query={"assembly_id": "GRCh38"},
    projection={"_id": 0}
)

# Export with aggregation
result = exporter.export_aggregation(
    collection="variants",
    pipeline=[
        {"$group": {"_id": "$reference_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ],
    output_path="chromosome_counts.json"
)
```

## Configuration API

### Settings Management

#### Loading Configuration

```python
from config.settings import load_config, validate_config

# Load configuration
config = load_config("config/settings.yaml")

# Validate configuration
is_valid, errors = validate_config(config)
```

#### Configuration Schema

```python
# MongoDB Configuration
mongodb_config = {
    "host": str,
    "port": int,
    "database": str,
    "username": str,          # optional
    "password": str,          # optional
    "uri": str,              # alternative to host/port
    "connection_timeout": int,
    "collections": {
        "variants": str,
        "individuals": str,
        "datasets": str,
        "biosamples": str,
        "analyses": str,
        "cohorts": str,
        "filtering_terms": str
    }
}

# VCF Processing Configuration
vcf_config = {
    "supported_assemblies": list,
    "default_assembly": str,
    "required_fields": list,
    "info_fields": list,
    "format_fields": list,
    "quality_filters": {
        "min_qual": float,
        "min_depth": int,
        "max_missing_rate": float,
        "min_allele_count": int,
        "max_allele_freq": float
    }
}

# Processing Configuration
processing_config = {
    "batch_size": int,
    "max_workers": int,
    "memory_limit": int,
    "temp_dir": str,
    "log_level": str,
    "show_progress": bool
}
```

## Utility Functions

### Common Utilities

#### File Handling

```python
from utils.file_utils import (
    read_json_file,
    write_json_file,
    read_csv_file,
    detect_file_format,
    validate_file_path
)

# Read JSON file
data = read_json_file("data.json")

# Write JSON file
write_json_file(data, "output.json", pretty=True)

# Read CSV with automatic delimiter detection
df = read_csv_file("data.csv")

# Detect file format
file_format = detect_file_format("data.xlsx")  # Returns 'excel'
```

#### Logging

```python
from utils.logging_utils import setup_logger, log_processing_stats

# Setup logger
logger = setup_logger("transformer", level="INFO")

# Log processing statistics
log_processing_stats(logger, {
    "total_records": 1000,
    "processed_records": 950,
    "errors": 5,
    "processing_time": 120.5
})
```

#### Progress Tracking

```python
from utils.progress_utils import ProgressTracker

# Initialize progress tracker
tracker = ProgressTracker(total=1000, description="Processing variants")

# Update progress
for i, record in enumerate(records):
    # Process record
    tracker.update(1)
    
# Finish
tracker.close()
```

#### Data Validation

```python
from utils.validation_utils import (
    validate_beacon_v2_record,
    validate_ontology_term,
    validate_genome_coordinates
)

# Validate Beacon v2 record
is_valid, errors = validate_beacon_v2_record(record, "variant")

# Validate ontology term
is_valid = validate_ontology_term("HP:0001250", "HPO")

# Validate genome coordinates
is_valid = validate_genome_coordinates("chr1", 100000, 100001, "GRCh38")
```

### Error Handling

#### Custom Exceptions

```python
from utils.exceptions import (
    BeaconTransformError,
    ValidationError,
    ConfigurationError,
    DataImportError
)

# Raise custom exceptions
raise BeaconTransformError("Failed to transform VCF record")
raise ValidationError("Invalid Beacon v2 format")
raise ConfigurationError("Missing required configuration")
raise DataImportError("MongoDB connection failed")
```

#### Error Context Manager

```python
from utils.error_handling import error_context

with error_context("VCF transformation"):
    # Code that might raise exceptions
    transformer.transform_vcf(vcf_path)
```

## Examples

### Complete Workflow Example

```python
from vcf_transform.vcf_to_beacon import VCFTransformer
from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer
from validation.validate_json import BeaconValidator
from data_import.import_to_mongo import MongoImporter

# 1. Transform VCF
vcf_transformer = VCFTransformer(assembly="GRCh38")
vcf_results = vcf_transformer.transform_vcf(
    vcf_path="input.vcf",
    output_dir="./output",
    metadata_path="individuals.csv"
)

# 2. Transform phenotypes
phenotype_transformer = PhenotypeTransformer()
phenotype_results = phenotype_transformer.transform_phenotypes(
    input_path="phenotypes.csv",
    output_dir="./output"
)

# 3. Validate data
validator = BeaconValidator()
validation_results = validator.validate_directory("./output")

# 4. Import to MongoDB (if validation passes)
if all(result.is_valid for result in validation_results):
    importer = MongoImporter(
        mongo_uri="mongodb://localhost:27017/",
        database="beacon_db"
    )
    import_results = importer.import_directory("./output")
    print("Data successfully imported to MongoDB")
else:
    print("Validation failed - check errors before importing")
```

For more examples, see the `examples/` directory. 