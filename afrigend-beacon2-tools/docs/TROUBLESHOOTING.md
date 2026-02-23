# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### 1. Python Version Compatibility

**Problem**: Tools require Python 3.8+ but older version is installed.

**Symptoms**:
```
SyntaxError: invalid syntax
TypeError: 'type' object is not subscriptable
```

**Solution**:
```bash
# Check Python version
python --version

# Install Python 3.8+ if needed
sudo apt update
sudo apt install python3.8 python3.8-venv python3.8-dev

# Create virtual environment with specific Python version
python3.8 -m venv venv
source venv/bin/activate
```

#### 2. Dependency Installation Failures

**Problem**: Failed to install required packages, especially pysam or cyvcf2.

**Symptoms**:
```
ERROR: Failed building wheel for pysam
ERROR: Failed building wheel for cyvcf2
```

**Solution**:
```bash
# Install system dependencies
sudo apt-get install build-essential python3-dev
sudo apt-get install zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev

# Update pip and build tools
pip install --upgrade pip setuptools wheel

# Install problematic packages individually
pip install pysam --no-binary pysam
pip install cyvcf2 --no-binary cyvcf2

# Then install remaining requirements
pip install -r requirements.txt
```

#### 3. Permission Issues

**Problem**: Permission denied when installing packages or running scripts.

**Symptoms**:
```
PermissionError: [Errno 13] Permission denied
```

**Solution**:
```bash
# Fix script permissions
chmod +x examples/*.sh
chmod -R 755 afrigend-beacon2-tools/

# Install packages in user space
pip install --user -r requirements.txt

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### VCF Processing Issues

#### 1. VCF Format Errors

**Problem**: VCF file format is invalid or corrupted.

**Symptoms**:
```
ValueError: Invalid VCF format
cyvcf2.cyvcf2.VCFError: malformed VCF
```

**Solution**:
```bash
# Validate VCF format
bcftools view -h input.vcf | head -20

# Check for common issues
grep -n "^#" input.vcf | tail -5  # Check header
head -20 input.vcf                # Check first records

# Fix common issues
# Remove extra spaces
sed 's/[[:space:]]\+/\t/g' input.vcf > fixed.vcf

# Sort VCF if needed
bcftools sort input.vcf -o sorted.vcf
```

#### 2. Memory Issues with Large VCF Files

**Problem**: Out of memory errors when processing large VCF files.

**Symptoms**:
```
MemoryError: Unable to allocate array
killed (signal 9)
```

**Solution**:
```bash
# Reduce batch size
python vcf_transform/vcf_to_beacon.py input.vcf \
    --batch-size 500 \
    --output ./output

# Use memory-efficient processing
python vcf_transform/vcf_to_beacon.py input.vcf \
    --memory-efficient \
    --temp-dir /fast/storage/temp
```

Update configuration:
```yaml
# config/settings.yaml
processing:
  batch_size: 500
  memory_limit: 1024
  max_workers: 2
```

#### 3. Assembly Mismatch

**Problem**: VCF assembly doesn't match specified assembly.

**Symptoms**:
```
ValueError: Assembly mismatch: VCF contains GRCh37 but GRCh38 specified
```

**Solution**:
```bash
# Check VCF header for assembly information
bcftools view -h input.vcf | grep "##reference"

# Specify correct assembly
python vcf_transform/vcf_to_beacon.py input.vcf \
    --assembly GRCh37 \
    --output ./output

# Or let tool auto-detect
python vcf_transform/vcf_to_beacon.py input.vcf \
    --auto-detect-assembly \
    --output ./output
```

#### 4. Missing Sample Metadata

**Problem**: Individual IDs in VCF don't match metadata file.

**Symptoms**:
```
KeyError: Sample 'SAMPLE001' not found in metadata
```

**Solution**:
```bash
# Check VCF sample names
bcftools query -l input.vcf

# Check metadata file headers
head -1 individuals.csv

# Create metadata template
python scripts/generate_metadata_template.py input.vcf > metadata_template.csv

# Validate metadata before processing
python scripts/validate_metadata.py individuals.csv input.vcf
```

### Phenotype Processing Issues

#### 1. Ontology Mapping Failures

**Problem**: Phenotype IDs cannot be mapped to known ontologies.

**Symptoms**:
```
WARNING: Unknown phenotype ID: HP:9999999
ERROR: Failed to map ontology term
```

**Solution**:
```bash
# Download latest ontology files
wget http://purl.obolibrary.org/obo/hp.obo
wget http://purl.obolibrary.org/obo/mondo.obo

# Use local ontology files
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --ontology-file hp.obo \
    --output ./output

# Enable lenient mode for unknown terms
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --lenient-ontology-mapping \
    --output ./output
```

#### 2. File Format Issues

**Problem**: Phenotype file format is not recognized or contains errors.

**Symptoms**:
```
UnicodeDecodeError: 'utf-8' codec can't decode
pandas.errors.ParserError: Error tokenizing data
```

**Solution**:
```bash
# Check file encoding
file -bi phenotypes.csv

# Convert encoding if needed
iconv -f ISO-8859-1 -t UTF-8 phenotypes.csv > phenotypes_utf8.csv

# Check CSV format
head -5 phenotypes.csv
csvlint phenotypes.csv

# Specify delimiter explicitly
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --delimiter ";" \
    --output ./output
```

#### 3. Missing Required Columns

**Problem**: Required columns are missing from phenotype file.

**Symptoms**:
```
KeyError: 'individual_id' column not found
ValueError: Missing required column: phenotype_id
```

**Solution**:
Check column names:
```bash
head -1 phenotypes.csv | tr ',' '\n' | nl
```

Map columns:
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --column-mapping individual_id:sample_id \
    --column-mapping phenotype_id:hpo_id \
    --output ./output
```

### MongoDB Issues

#### 1. Connection Failures

**Problem**: Cannot connect to MongoDB server.

**Symptoms**:
```
pymongo.errors.ServerSelectionTimeoutError: No servers available
pymongo.errors.ConnectionFailure: Connection refused
```

**Solution**:
```bash
# Check MongoDB status
sudo systemctl status mongod

# Start MongoDB if not running
sudo systemctl start mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Test connection
mongosh --eval "db.adminCommand('ismaster')"

# Check firewall
sudo ufw status
sudo ufw allow 27017
```

#### 2. Authentication Issues

**Problem**: Authentication failed when connecting to MongoDB.

**Symptoms**:
```
pymongo.errors.OperationFailure: Authentication failed
```

**Solution**:
```bash
# Create user in MongoDB
mongosh
use beacon_db
db.createUser({
  user: "beacon_user",
  pwd: "secure_password",
  roles: [{ role: "readWrite", db: "beacon_db" }]
})

# Update configuration
# config/settings.yaml
mongodb:
  username: "beacon_user"
  password: "secure_password"
  auth_source: "beacon_db"
```

#### 3. Import Performance Issues

**Problem**: Data import is very slow or times out.

**Symptoms**:
```
Slow import: 10 records/second
pymongo.errors.NetworkTimeout: timed out
```

**Solution**:
```bash
# Increase batch size
python data_import/import_to_mongo.py data.json \
    --batch-size 10000 \
    --db beacon_db

# Use bulk operations
python data_import/import_to_mongo.py data.json \
    --bulk-operations \
    --db beacon_db

# Create indexes after import
python data_import/import_to_mongo.py data.json \
    --create-indexes-after \
    --db beacon_db
```

Update MongoDB configuration:
```javascript
// /etc/mongod.conf
net:
  maxIncomingConnections: 65536
operationProfiling:
  slowOpThresholdMs: 100
```

### Validation Issues

#### 1. Schema Validation Failures

**Problem**: JSON data doesn't conform to Beacon v2 schema.

**Symptoms**:
```
jsonschema.exceptions.ValidationError: 'assembly_id' is a required property
```

**Solution**:
```bash
# Use lenient validation to identify issues
python validation/validate_json.py data.json \
    --lenient \
    --verbose

# Fix common schema issues
python scripts/fix_beacon_schema.py data.json > fixed_data.json

# Validate with specific schema version
python validation/validate_json.py data.json \
    --schema-version 2.0.0
```

#### 2. Data Type Mismatches

**Problem**: Data types don't match expected schema types.

**Symptoms**:
```
ValidationError: 123 is not of type 'string'
ValidationError: 'invalid_date' is not a valid date-time
```

**Solution**:
```bash
# Enable automatic type conversion
python validation/validate_json.py data.json \
    --auto-convert-types \
    --schema-type variant

# Check data types in source
python scripts/analyze_data_types.py data.json
```

### Performance Issues

#### 1. Slow Processing

**Problem**: Data transformation is taking too long.

**Symptoms**:
- Processing speed < 100 records/second
- High CPU usage but low throughput

**Solution**:
```yaml
# Optimize configuration
processing:
  batch_size: 5000        # Increase batch size
  max_workers: 8          # Use more cores
  memory_limit: 4096      # Allocate more memory
  use_parallel_processing: true
```

```bash
# Use faster storage for temporary files
python vcf_transform/vcf_to_beacon.py input.vcf \
    --temp-dir /dev/shm \
    --output ./output

# Enable performance profiling
python vcf_transform/vcf_to_beacon.py input.vcf \
    --profile \
    --output ./output
```

#### 2. High Memory Usage

**Problem**: Process consumes too much memory.

**Symptoms**:
- Memory usage > 8GB
- System becomes unresponsive
- Out of memory errors

**Solution**:
```yaml
# Reduce memory usage
processing:
  batch_size: 1000        # Smaller batches
  max_workers: 2          # Fewer processes
  memory_limit: 2048      # Limit per process
  streaming_mode: true    # Process in streaming mode
```

```bash
# Monitor memory usage
python vcf_transform/vcf_to_beacon.py input.vcf \
    --monitor-memory \
    --output ./output

# Use memory profiler
pip install memory-profiler
python -m memory_profiler vcf_transform/vcf_to_beacon.py input.vcf
```

### Data Quality Issues

#### 1. Inconsistent Data

**Problem**: Data contains inconsistencies or errors.

**Symptoms**:
```
WARNING: Inconsistent chromosome naming: chr1 vs 1
ERROR: Invalid coordinate: start > end
```

**Solution**:
```bash
# Enable data cleaning
python vcf_transform/vcf_to_beacon.py input.vcf \
    --clean-data \
    --normalize-chromosomes \
    --output ./output

# Generate data quality report
python scripts/data_quality_report.py input.vcf > quality_report.html
```

#### 2. Missing Required Fields

**Problem**: Required fields are missing from input data.

**Symptoms**:
```
KeyError: Required field 'reference_bases' not found
```

**Solution**:
```bash
# Check data completeness
python scripts/check_data_completeness.py input.vcf

# Fill missing fields with defaults
python vcf_transform/vcf_to_beacon.py input.vcf \
    --fill-missing-fields \
    --output ./output
```

## Diagnostic Tools

### 1. System Information

```bash
# Check system resources
python scripts/system_info.py

# Check Python environment
python scripts/check_environment.py

# Test all dependencies
python scripts/test_dependencies.py
```

### 2. Data Analysis

```bash
# Analyze VCF file
python scripts/analyze_vcf.py input.vcf

# Analyze phenotype data
python scripts/analyze_phenotypes.py phenotypes.csv

# Check data compatibility
python scripts/check_compatibility.py input.vcf individuals.csv
```

### 3. Performance Profiling

```bash
# Profile memory usage
python -m memory_profiler vcf_transform/vcf_to_beacon.py input.vcf

# Profile CPU usage
python -m cProfile -o profile.stats vcf_transform/vcf_to_beacon.py input.vcf

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(10)
"
```

## Getting Help

### 1. Enable Debug Logging

```yaml
# config/settings.yaml
processing:
  log_level: "DEBUG"
  log_file: "debug.log"
```

### 2. Collect System Information

```bash
# Generate support bundle
python scripts/generate_support_bundle.py > support_info.txt
```

### 3. Test with Sample Data

```bash
# Download sample data
python scripts/download_sample_data.py

# Test with sample data
python scripts/test_with_samples.py
```

### 4. Contact Support

When reporting issues, please include:

1. **System Information**:
   - Operating system and version
   - Python version
   - Installed package versions

2. **Configuration**:
   - Configuration file (remove sensitive data)
   - Command line arguments used

3. **Error Information**:
   - Complete error messages
   - Log files (if available)
   - Steps to reproduce the issue

4. **Data Information**:
   - File sizes and formats
   - Sample data (if possible to share)
   - Processing parameters used

### 5. Common Commands for Debugging

```bash
# Check file formats
file input.vcf
head -20 input.vcf

# Check file sizes
ls -lh input.vcf
du -sh ./output/

# Check system resources
free -h
df -h
top

# Check network connectivity (for MongoDB Atlas)
ping cluster.mongodb.net
telnet cluster.mongodb.net 27017

# Check MongoDB status
sudo systemctl status mongod
mongosh --eval "db.stats()"
```

For additional support, please check the [FAQ](FAQ.md) or open an issue on GitHub. 