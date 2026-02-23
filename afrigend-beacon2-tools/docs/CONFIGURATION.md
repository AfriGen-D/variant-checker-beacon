# Configuration Guide

## Overview

The AfriGend Beacon v2 Tools use a centralized YAML configuration file (`config/settings.yaml`) to manage all processing parameters, database connections, and tool behaviors.

## Configuration File Structure

### Complete Configuration Template

```yaml
# AfriGend Beacon v2 Data Transformation Tools Configuration

# MongoDB Connection Settings
mongodb:
  host: "localhost"
  port: 27017
  database: "beacon_db"
  username: "beacon_user"          # Optional
  password: "secure_password"      # Optional
  auth_source: "admin"             # Optional
  uri: ""                          # Alternative to host/port
  connection_timeout: 30
  max_pool_size: 10
  collections:
    variants: "variants"
    individuals: "individuals"
    datasets: "datasets"
    biosamples: "biosamples"
    analyses: "analyses"
    cohorts: "cohorts"
    filtering_terms: "filtering_terms"

# VCF Processing Settings
vcf:
  # Supported genome assemblies
  supported_assemblies:
    - "GRCh37"
    - "GRCh38"
    - "hg19"
    - "hg38"
  
  # Default assembly if not specified
  default_assembly: "GRCh38"
  
  # VCF fields to extract
  required_fields:
    - "CHROM"
    - "POS"
    - "REF"
    - "ALT"
    - "QUAL"
    - "FILTER"
  
  # INFO fields to extract (optional)
  info_fields:
    - "AF"        # Allele Frequency
    - "AC"        # Allele Count
    - "AN"        # Allele Number
    - "DP"        # Total Depth
    - "GENE"      # Gene Symbol
    - "CSQ"       # Consequence (VEP)
    - "ANN"       # Annotation (SnpEff)
  
  # FORMAT fields to extract
  format_fields:
    - "GT"        # Genotype
    - "DP"        # Depth
    - "GQ"        # Genotype Quality
    - "AD"        # Allelic Depths
  
  # Quality filters
  quality_filters:
    min_qual: 20
    min_depth: 10
    max_missing_rate: 0.1
    min_allele_count: 1
    max_allele_freq: 0.99

# Phenotype Processing Settings
phenotypes:
  # Supported ontologies
  supported_ontologies:
    - "HPO"       # Human Phenotype Ontology
    - "MONDO"     # Monarch Disease Ontology
    - "ORDO"      # Orphanet Rare Disease Ontology
    - "NCIT"      # NCI Thesaurus
    - "SNOMED"    # SNOMED CT
  
  # Default ontology mapping
  default_ontology: "HPO"
  
  # Phenotype file formats
  supported_formats:
    - "csv"
    - "tsv"
    - "xlsx"
    - "json"
    - "phenopackets"

# Data Validation Settings
validation:
  # Strict mode (fail on any validation error)
  strict_mode: false
  
  # Required fields validation
  required_fields_check: true
  
  # Data type validation
  type_validation: true
  
  # Range validation for numeric fields
  range_validation: true
  
  # Reference genome validation
  genome_validation: true

# Processing Settings
processing:
  # Batch size for bulk operations
  batch_size: 1000
  
  # Number of parallel processes
  max_workers: 4
  
  # Memory limit per process (MB)
  memory_limit: 2048
  
  # Temporary directory for processing
  temp_dir: "/tmp/beacon_transform"
  
  # Log level (DEBUG, INFO, WARNING, ERROR)
  log_level: "INFO"
  
  # Progress reporting
  show_progress: true

# Output Settings
output:
  # Default output format
  default_format: "json"
  
  # Supported output formats
  supported_formats:
    - "json"
    - "bson"
    - "csv"
    - "tsv"
  
  # Pretty print JSON output
  pretty_json: true
  
  # Include metadata in output
  include_metadata: true

# Data Sources
data_sources:
  # External ontology sources
  ontologies:
    hpo_url: "https://hpo.jax.org/api/hpo/term/"
    mondo_url: "https://www.ebi.ac.uk/ols/api/ontologies/mondo/terms/"
  
  # Reference genome sources
  reference_genomes:
    grch37_url: "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/"
    grch38_url: "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.28_GRCh38.p13/"
```

## Configuration Sections

### 1. MongoDB Configuration

#### Basic Connection
```yaml
mongodb:
  host: "localhost"
  port: 27017
  database: "beacon_db"
```

#### With Authentication
```yaml
mongodb:
  host: "localhost"
  port: 27017
  database: "beacon_db"
  username: "beacon_user"
  password: "secure_password"
  auth_source: "admin"
```

#### Using Connection URI
```yaml
mongodb:
  uri: "mongodb://username:password@localhost:27017/beacon_db"
```

#### Cloud MongoDB (Atlas)
```yaml
mongodb:
  uri: "mongodb+srv://username:password@cluster.mongodb.net/beacon_db"
  connection_timeout: 30
  max_pool_size: 20
```

#### Collection Mapping
```yaml
mongodb:
  collections:
    variants: "genomic_variants"      # Custom collection name
    individuals: "study_participants"
    datasets: "beacon_datasets"
    biosamples: "biological_samples"
```

### 2. VCF Processing Configuration

#### Assembly Settings
```yaml
vcf:
  supported_assemblies:
    - "GRCh37"
    - "GRCh38"
    - "hg19"
    - "hg38"
  default_assembly: "GRCh38"
```

#### Field Extraction
```yaml
vcf:
  # Always extract these fields
  required_fields:
    - "CHROM"
    - "POS"
    - "REF"
    - "ALT"
    - "QUAL"
    - "FILTER"
  
  # Extract these INFO fields if present
  info_fields:
    - "AF"        # Allele Frequency
    - "AC"        # Allele Count
    - "AN"        # Allele Number
    - "DP"        # Total Depth
    - "GENE"      # Gene Symbol
    - "CSQ"       # VEP Consequence
    - "ANN"       # SnpEff Annotation
    - "CADD"      # CADD Score
    - "SIFT"      # SIFT Score
    - "POLYPHEN"  # PolyPhen Score
  
  # Extract these FORMAT fields
  format_fields:
    - "GT"        # Genotype
    - "DP"        # Depth
    - "GQ"        # Genotype Quality
    - "AD"        # Allelic Depths
    - "PL"        # Phred-scaled Likelihoods
```

#### Quality Filtering
```yaml
vcf:
  quality_filters:
    min_qual: 30              # Minimum variant quality score
    min_depth: 20             # Minimum read depth
    max_missing_rate: 0.05    # Maximum missing genotype rate
    min_allele_count: 2       # Minimum allele count
    max_allele_freq: 0.95     # Maximum allele frequency
    min_genotype_quality: 20  # Minimum genotype quality
```

### 3. Phenotype Processing Configuration

#### Ontology Settings
```yaml
phenotypes:
  supported_ontologies:
    - "HPO"       # Human Phenotype Ontology
    - "MONDO"     # Monarch Disease Ontology
    - "ORDO"      # Orphanet Rare Disease Ontology
    - "NCIT"      # NCI Thesaurus
    - "SNOMED"    # SNOMED CT
    - "ICD10"     # ICD-10
    - "ICD11"     # ICD-11
  
  default_ontology: "HPO"
  
  # Ontology file locations (local or remote)
  ontology_sources:
    hpo_file: "/path/to/hp.obo"
    mondo_file: "/path/to/mondo.obo"
    ordo_file: "/path/to/ordo.obo"
```

#### Input Format Support
```yaml
phenotypes:
  supported_formats:
    - "csv"
    - "tsv"
    - "xlsx"
    - "json"
    - "phenopackets"
  
  # Default column mappings for CSV/TSV
  column_mappings:
    individual_id: ["individual_id", "sample_id", "participant_id"]
    phenotype_id: ["phenotype_id", "hpo_id", "term_id"]
    phenotype_label: ["phenotype_label", "term_label", "description"]
    onset_age: ["onset_age", "age_onset", "age_at_onset"]
    severity: ["severity", "severity_level"]
    evidence: ["evidence", "evidence_type", "evidence_code"]
```

### 4. Validation Configuration

#### Validation Modes
```yaml
validation:
  strict_mode: false              # Fail on any validation error
  required_fields_check: true     # Check required fields
  type_validation: true           # Validate data types
  range_validation: true          # Validate numeric ranges
  genome_validation: true         # Validate genome coordinates
  ontology_validation: true       # Validate ontology terms
```

#### Custom Validation Rules
```yaml
validation:
  custom_rules:
    variant_coordinates:
      max_chromosome_length: 300000000
      valid_chromosomes: ["1", "2", "3", ..., "22", "X", "Y", "MT"]
    
    individual_data:
      valid_sexes: ["male", "female", "unknown"]
      age_range: [0, 120]
    
    phenotype_data:
      required_ontology_prefixes: ["HP:", "MONDO:", "ORDO:"]
```

### 5. Processing Configuration

#### Performance Settings
```yaml
processing:
  batch_size: 5000              # Records per batch
  max_workers: 8                # Parallel processes
  memory_limit: 4096            # MB per process
  use_multiprocessing: true     # Enable multiprocessing
  chunk_size: 1000              # Chunk size for parallel processing
```

#### Resource Management
```yaml
processing:
  temp_dir: "/fast/storage/temp"  # Fast storage for temp files
  cleanup_temp_files: true       # Clean up temporary files
  max_temp_space: 10240          # Maximum temp space (MB)
  
  # Memory management
  gc_threshold: 1000             # Garbage collection threshold
  memory_monitoring: true        # Monitor memory usage
```

#### Logging Configuration
```yaml
processing:
  log_level: "INFO"              # DEBUG, INFO, WARNING, ERROR
  log_file: "beacon_transform.log"
  log_rotation: true
  max_log_size: "10MB"
  backup_count: 5
  
  # Progress reporting
  show_progress: true
  progress_update_interval: 100  # Update every N records
```

### 6. Output Configuration

#### Format Settings
```yaml
output:
  default_format: "json"
  supported_formats:
    - "json"
    - "jsonl"      # JSON Lines
    - "bson"       # Binary JSON
    - "csv"
    - "tsv"
    - "parquet"    # Apache Parquet
  
  # JSON formatting
  pretty_json: true
  json_indent: 2
  ensure_ascii: false
```

#### File Organization
```yaml
output:
  directory_structure:
    variants: "variants/"
    individuals: "individuals/"
    phenotypes: "phenotypes/"
    metadata: "metadata/"
  
  file_naming:
    timestamp: true              # Include timestamp in filenames
    batch_numbering: true        # Number batch files
    compression: "gzip"          # Compress output files
```

## Environment-Specific Configurations

### Development Environment
```yaml
# config/development.yaml
processing:
  batch_size: 100
  max_workers: 2
  log_level: "DEBUG"
  show_progress: true

validation:
  strict_mode: false

mongodb:
  database: "beacon_dev"
```

### Production Environment
```yaml
# config/production.yaml
processing:
  batch_size: 10000
  max_workers: 16
  log_level: "INFO"
  memory_limit: 8192

validation:
  strict_mode: true

mongodb:
  database: "beacon_production"
  connection_timeout: 60
  max_pool_size: 50
```

### Testing Environment
```yaml
# config/testing.yaml
processing:
  batch_size: 10
  max_workers: 1
  log_level: "DEBUG"

validation:
  strict_mode: true

mongodb:
  database: "beacon_test"
```

## Configuration Loading

### Python API
```python
from config.settings import load_config

# Load default configuration
config = load_config()

# Load specific configuration file
config = load_config("config/production.yaml")

# Load with environment override
config = load_config(environment="production")
```

### Environment Variables

Override configuration with environment variables:

```bash
# MongoDB settings
export BEACON_MONGODB_HOST="production-server"
export BEACON_MONGODB_PORT="27017"
export BEACON_MONGODB_DATABASE="beacon_prod"
export BEACON_MONGODB_USERNAME="prod_user"
export BEACON_MONGODB_PASSWORD="secure_password"

# Processing settings
export BEACON_PROCESSING_BATCH_SIZE="5000"
export BEACON_PROCESSING_MAX_WORKERS="8"
export BEACON_PROCESSING_LOG_LEVEL="INFO"

# VCF settings
export BEACON_VCF_DEFAULT_ASSEMBLY="GRCh38"
export BEACON_VCF_MIN_QUAL="30"
```

### Configuration Validation

```python
from config.settings import validate_config

# Validate configuration
config = load_config()
is_valid, errors = validate_config(config)

if not is_valid:
    for error in errors:
        print(f"Configuration error: {error}")
```

## Best Practices

### 1. Security
- Store sensitive credentials in environment variables
- Use encrypted connections for production databases
- Implement proper access controls

### 2. Performance
- Adjust batch sizes based on available memory
- Use appropriate number of worker processes
- Monitor resource usage during processing

### 3. Reliability
- Enable strict validation for production
- Implement proper error handling
- Use connection pooling for database operations

### 4. Maintainability
- Use environment-specific configuration files
- Document custom configuration changes
- Version control configuration files

## Troubleshooting

### Common Configuration Issues

1. **MongoDB Connection Failures**
   ```yaml
   mongodb:
     connection_timeout: 60    # Increase timeout
     max_pool_size: 20        # Increase pool size
   ```

2. **Memory Issues**
   ```yaml
   processing:
     batch_size: 500          # Reduce batch size
     memory_limit: 1024       # Reduce memory limit
   ```

3. **Performance Issues**
   ```yaml
   processing:
     max_workers: 1           # Reduce parallelism
     batch_size: 10000        # Increase batch size
   ```

For more troubleshooting guidance, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md). 