# Afrigend Beacon2 Tools

Comprehensive data management utilities for the Afrigen Beacon v2 implementation.

## Overview

This toolkit provides utilities for transforming, importing, exporting, and validating genomic data for the GA4GH Beacon v2 API.

**Key Features**:
- VCF to Beacon v2 JSON conversion
- Phenotype data transformation
- Bulk data import to MongoDB
- Data export (JSON, VCF, CSV)
- JSON schema validation
- Batch processing workflows

---

## Table of Contents

1. [Installation](#installation)
2. [VCF Transformation](#vcf-transformation)
3. [Phenotype Transformation](#phenotype-transformation)
4. [Data Import](#data-import)
5. [Data Export](#data-export)
6. [Data Validation](#data-validation)
7. [Complete Workflows](#complete-workflows)
8. [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- Python 3.8+
- MongoDB 5.0+ (for import/export)
- Access to Beacon API (for testing)

### Install Dependencies

```bash
cd afrigend-beacon2-tools
pip install -r requirements.txt
```

**requirements.txt**:
```
pysam==0.21.0
pandas==2.0.0
jsonschema==4.17.3
click==8.1.3
tqdm==4.65.0
pymongo==4.3.3
```

### Verify Installation

```bash
python vcf_transform/vcf_to_beacon.py --version
```

---

## VCF Transformation

### Overview

Convert VCF (Variant Call Format) files to GA4GH Beacon v2 JSON format.

**Location**: `vcf_transform/vcf_to_beacon.py`

**Supported Formats**:
- VCF 4.0, 4.1, 4.2, 4.3
- Compressed VCF (.vcf.gz, .bcf)
- Multi-sample VCF
- Annotated VCF (VEP, SnpEff)

### Basic Usage

```bash
python vcf_transform/vcf_to_beacon.py \
  input.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset dataset_001
```

### Advanced Options

```bash
python vcf_transform/vcf_to_beacon.py \
  input.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset dataset_001 \
  --batch-size 10000 \
  --workers 4 \
  --annotations vep \
  --filter-pass-only \
  --min-qual 30
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input` | Yes | - | Input VCF file path |
| `--output` | Yes | - | Output JSON file path |
| `--assembly` | Yes | - | Reference assembly (GRCh38, GRCh37) |
| `--dataset` | Yes | - | Dataset ID |
| `--batch-size` | No | 10000 | Records per batch |
| `--workers` | No | 1 | Parallel workers |
| `--annotations` | No | none | Annotation format (vep, snpeff) |
| `--filter-pass-only` | No | False | Only PASS filter variants |
| `--min-qual` | No | 0 | Minimum quality score |

### Output Format

```json
[
  {
    "id": "variant_chr1_100000_A_T",
    "assemblyId": "GRCh38",
    "referenceName": "1",
    "start": 100000,
    "end": 100001,
    "referenceBases": "A",
    "alternateBases": "T",
    "variantType": "SNP",
    "info": {
      "gene_symbol": "GENE1",
      "consequence": "missense_variant",
      "allele_frequency": 0.001
    },
    "caseLevelData": [
      {
        "biosampleId": "sample_001",
        "genotype": "0/1",
        "quality": 99.0,
        "depth": 50
      }
    ]
  }
]
```

### Examples

**Single Sample VCF**:
```bash
python vcf_transform/vcf_to_beacon.py \
  sample.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset my_dataset
```

**Multi-Sample VCF**:
```bash
python vcf_transform/vcf_to_beacon.py \
  cohort.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset cohort_study \
  --batch-size 50000 \
  --workers 8
```

**VEP Annotated VCF**:
```bash
python vcf_transform/vcf_to_beacon.py \
  annotated.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset annotated_dataset \
  --annotations vep
```

### Performance

| Dataset Size | Processing Time | Memory Usage |
|--------------|-----------------|--------------|
| 100K variants | ~2 minutes | ~500 MB |
| 1M variants | ~15 minutes | ~2 GB |
| 10M variants | ~2 hours | ~8 GB |
| 100M variants | ~20 hours | ~32 GB |

**Optimization Tips**:
- Use `--batch-size 50000` for large files
- Use `--workers 8` for multi-core processing
- Use `--filter-pass-only` to reduce output size

---

## Phenotype Transformation

### Overview

Transform phenotype data (CSV/TSV) to Beacon v2 Individual and Biosample JSON.

**Location**: `phenotype_transform/phenotype_to_beacon.py`

**Supported Formats**:
- CSV, TSV
- Excel (.xlsx)
- Custom delimited files

### Basic Usage

```bash
python phenotype_transform/phenotype_to_beacon.py \
  phenotypes.csv \
  --output individuals.json \
  --mapping-config mapping.yaml \
  --dataset dataset_001
```

### Mapping Configuration

**mapping.yaml**:
```yaml
# Field mapping configuration
individual:
  id: subject_id
  sex: gender
  ethnicity: ethnicity_code
  diseases:
    - field: disease_code
      ontology: MONDO
    - field: disease_name
      ontology: text
  phenotypic_features:
    - field: phenotype_hpo
      ontology: HPO

biosample:
  id: sample_id
  individual_id: subject_id
  sample_origin_detail: tissue_type
  collection_date: collection_date
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input` | Yes | - | Input CSV/TSV file |
| `--output` | Yes | - | Output JSON file |
| `--mapping-config` | Yes | - | Field mapping YAML |
| `--dataset` | Yes | - | Dataset ID |
| `--entry-type` | No | individuals | Entry type (individuals, biosamples) |

### Output Format

**Individuals JSON**:
```json
[
  {
    "id": "individual_001",
    "sex": "FEMALE",
    "ethnicity": {
      "id": "NCIT:C42331",
      "label": "African"
    },
    "diseases": [
      {
        "diseaseCode": {
          "id": "MONDO:0007254",
          "label": "breast carcinoma"
        }
      }
    ],
    "phenotypicFeatures": [
      {
        "featureType": {
          "id": "HP:0000716",
          "label": "Depression"
        }
      }
    ]
  }
]
```

### Examples

**Transform Individuals**:
```bash
python phenotype_transform/phenotype_to_beacon.py \
  subjects.csv \
  --output individuals.json \
  --mapping-config mappings/subject_mapping.yaml \
  --dataset study_001
```

**Transform Biosamples**:
```bash
python phenotype_transform/phenotype_to_beacon.py \
  samples.csv \
  --output biosamples.json \
  --mapping-config mappings/biosample_mapping.yaml \
  --dataset study_001 \
  --entry-type biosamples
```

---

## Data Import

### Overview

Bulk import Beacon JSON data to MongoDB.

**Location**: `data_import/import_to_mongo.py`

**Features**:
- Batch insertion for performance
- Error handling and rollback
- Progress reporting
- Duplicate detection
- Validation before import

### Basic Usage

```bash
python data_import/import_to_mongo.py \
  variants.json \
  --collection variants \
  --batch-size 1000
```

### Advanced Options

```bash
python data_import/import_to_mongo.py \
  variants.json \
  --collection variants \
  --batch-size 5000 \
  --mode upsert \
  --validate \
  --create-indexes \
  --mongodb-uri mongodb://localhost:27017/beacon_db
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input` | Yes | - | Input JSON file |
| `--collection` | Yes | - | MongoDB collection |
| `--batch-size` | No | 1000 | Records per batch |
| `--mode` | No | insert | Import mode (insert, upsert, replace) |
| `--validate` | No | False | Validate before import |
| `--create-indexes` | No | False | Create indexes after import |
| `--mongodb-uri` | No | env | MongoDB connection URI |

### Import Modes

**insert**: Insert new records (fail on duplicates)
```bash
python data_import/import_to_mongo.py variants.json --collection variants --mode insert
```

**upsert**: Update existing or insert new
```bash
python data_import/import_to_mongo.py variants.json --collection variants --mode upsert
```

**replace**: Delete all and import fresh
```bash
python data_import/import_to_mongo.py variants.json --collection variants --mode replace
```

### Examples

**Import Variants**:
```bash
python data_import/import_to_mongo.py \
  variants.json \
  --collection variants \
  --batch-size 10000 \
  --create-indexes
```

**Import Individuals**:
```bash
python data_import/import_to_mongo.py \
  individuals.json \
  --collection individuals \
  --mode upsert \
  --validate
```

**Import with Custom MongoDB**:
```bash
python data_import/import_to_mongo.py \
  variants.json \
  --collection variants \
  --mongodb-uri mongodb://user:pass@host:27017/beacon_db?authSource=admin
```

### Performance

**Import Speed**:
- ~10,000 variants/second (batch-size 10000)
- ~50,000 variants/second (batch-size 50000, no validation)

**Memory Usage**:
- ~500 MB for 1M variants
- Scales linearly with batch size

### Progress Output

```
Importing data from variants.json...
Collection: variants
Mode: insert
Batch size: 10000

Progress: 100000 / 1000000 (10%)
Progress: 200000 / 1000000 (20%)
...
Progress: 1000000 / 1000000 (100%)

Import complete!
Total records: 1000000
Time elapsed: 120 seconds
Records/second: 8333
```

---

## Data Export

### Overview

Export data from MongoDB to various formats.

**Location**: `data_export/export_from_mongo.py`

**Supported Formats**:
- JSON (Beacon v2 format)
- VCF (for variants)
- CSV (for all entry types)
- TSV

### Basic Usage

**Export to JSON**:
```bash
python data_export/export_from_mongo.py \
  --collection variants \
  --output backup.json
```

**Export to VCF**:
```bash
python data_export/export_to_vcf.py \
  --collection variants \
  --output export.vcf.gz \
  --assembly GRCh38
```

**Export to CSV**:
```bash
python data_export/export_to_csv.py \
  --collection individuals \
  --output individuals.csv
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--collection` | Yes | - | MongoDB collection |
| `--output` | Yes | - | Output file path |
| `--filter` | No | {} | MongoDB query filter (JSON) |
| `--limit` | No | 0 | Max records (0 = all) |
| `--assembly` | No | GRCh38 | Assembly (VCF export) |
| `--mongodb-uri` | No | env | MongoDB connection |

### Filtering Exports

**Export Specific Dataset**:
```bash
python data_export/export_from_mongo.py \
  --collection variants \
  --output dataset_001_variants.json \
  --filter '{"dataset_id": "dataset_001"}'
```

**Export Chromosome**:
```bash
python data_export/export_from_mongo.py \
  --collection variants \
  --output chr1_variants.json \
  --filter '{"reference_name": "1"}'
```

**Export Region**:
```bash
python data_export/export_from_mongo.py \
  --collection variants \
  --output region_variants.json \
  --filter '{"reference_name": "1", "start": {"$gte": 100000, "$lte": 200000}}'
```

### Examples

**Full Backup**:
```bash
# Export all collections
for collection in variants individuals biosamples datasets cohorts analyses; do
  python data_export/export_from_mongo.py \
    --collection $collection \
    --output backup_${collection}.json
done
```

**VCF Export**:
```bash
python data_export/export_to_vcf.py \
  --collection variants \
  --output export.vcf.gz \
  --assembly GRCh38 \
  --filter '{"dataset_id": "dataset_001"}'
```

**CSV Export for Analysis**:
```bash
python data_export/export_to_csv.py \
  --collection individuals \
  --output individuals.csv \
  --fields id,sex,ethnicity,diseases
```

---

## Data Validation

### Overview

Validate JSON data against GA4GH Beacon v2 schemas.

**Location**: `validation/validate_json.py`

**Features**:
- JSON Schema validation
- Beacon v2 compliance checking
- Detailed error reporting
- Batch validation

### Basic Usage

```bash
python validation/validate_json.py \
  variants.json \
  --schema schemas/beacon-v2-variant.json
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input` | Yes | - | Input JSON file |
| `--schema` | No | auto | JSON schema file |
| `--entry-type` | No | auto | Entry type (variant, individual, etc.) |
| `--strict` | No | False | Strict validation |
| `--output-errors` | No | None | Write errors to file |

### Built-in Schemas

```bash
validation/schemas/
├── beacon-v2-variant.json
├── beacon-v2-individual.json
├── beacon-v2-biosample.json
├── beacon-v2-dataset.json
├── beacon-v2-cohort.json
└── beacon-v2-analysis.json
```

### Examples

**Validate Variants**:
```bash
python validation/validate_json.py \
  variants.json \
  --entry-type variant
```

**Validate with Error Output**:
```bash
python validation/validate_json.py \
  variants.json \
  --entry-type variant \
  --output-errors errors.json
```

**Strict Validation**:
```bash
python validation/validate_json.py \
  variants.json \
  --entry-type variant \
  --strict
```

### Validation Output

**Success**:
```
Validating variants.json...
Entry type: genomicVariant
Schema: beacon-v2-variant.json

Validation: PASSED
Total records: 1000
Valid records: 1000
Invalid records: 0
```

**Errors**:
```
Validating variants.json...
Entry type: genomicVariant
Schema: beacon-v2-variant.json

Validation: FAILED
Total records: 1000
Valid records: 995
Invalid records: 5

Errors:
Record 100: 'start' is required
Record 250: 'assemblyId' must be one of ['GRCh38', 'GRCh37']
Record 500: 'referenceBases' does not match pattern '^[ACGTN]+$'
Record 750: Additional property 'invalid_field' not allowed
Record 900: 'start' must be >= 0
```

---

## Complete Workflows

### Workflow 1: VCF Import Pipeline

**Goal**: Import VCF file to Beacon API

```bash
#!/bin/bash
# complete_vcf_import.sh

# Step 1: Transform VCF to Beacon JSON
echo "Step 1: Transforming VCF..."
python vcf_transform/vcf_to_beacon.py \
  input.vcf.gz \
  --output variants.json \
  --assembly GRCh38 \
  --dataset dataset_001 \
  --batch-size 10000

# Step 2: Validate JSON
echo "Step 2: Validating..."
python validation/validate_json.py \
  variants.json \
  --entry-type variant

# Step 3: Import to MongoDB
echo "Step 3: Importing to MongoDB..."
python data_import/import_to_mongo.py \
  variants.json \
  --collection variants \
  --batch-size 10000 \
  --create-indexes

# Step 4: Verify import
echo "Step 4: Verifying..."
mongo beacon_db --eval "db.variants.count()"

echo "Import complete!"
```

### Workflow 2: Phenotype Data Integration

```bash
#!/bin/bash
# import_phenotypes.sh

# Step 1: Transform phenotypes to individuals
echo "Transforming phenotypes..."
python phenotype_transform/phenotype_to_beacon.py \
  phenotypes.csv \
  --output individuals.json \
  --mapping-config mappings/phenotype_mapping.yaml \
  --dataset dataset_001

# Step 2: Transform biosamples
echo "Transforming biosamples..."
python phenotype_transform/phenotype_to_beacon.py \
  biosamples.csv \
  --output biosamples.json \
  --mapping-config mappings/biosample_mapping.yaml \
  --dataset dataset_001 \
  --entry-type biosamples

# Step 3: Validate
python validation/validate_json.py individuals.json --entry-type individual
python validation/validate_json.py biosamples.json --entry-type biosample

# Step 4: Import
python data_import/import_to_mongo.py individuals.json --collection individuals
python data_import/import_to_mongo.py biosamples.json --collection biosamples

echo "Phenotype import complete!"
```

### Workflow 3: Data Backup and Restore

**Backup**:
```bash
#!/bin/bash
# backup_beacon_data.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR=backup_${DATE}

mkdir -p $BACKUP_DIR

# Export all collections
for collection in variants individuals biosamples datasets cohorts analyses; do
  echo "Backing up $collection..."
  python data_export/export_from_mongo.py \
    --collection $collection \
    --output $BACKUP_DIR/${collection}.json
done

# Compress backup
tar -czf ${BACKUP_DIR}.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup saved to ${BACKUP_DIR}.tar.gz"
```

**Restore**:
```bash
#!/bin/bash
# restore_beacon_data.sh

BACKUP_FILE=$1

# Extract backup
tar -xzf $BACKUP_FILE

BACKUP_DIR=$(basename $BACKUP_FILE .tar.gz)

# Restore all collections
for file in $BACKUP_DIR/*.json; do
  collection=$(basename $file .json)
  echo "Restoring $collection..."
  python data_import/import_to_mongo.py \
    $file \
    --collection $collection \
    --mode replace
done

echo "Restore complete!"
```

---

## Troubleshooting

### Common Issues

**Issue: "pysam not found"**
```bash
# Solution: Install with conda (recommended for pysam)
conda install -c bioconda pysam
# Or pip
pip install pysam==0.21.0
```

**Issue: "MongoDB connection refused"**
```bash
# Solution: Check MongoDB is running
docker ps | grep mongodb
# Or
systemctl status mongodb
```

**Issue: "Out of memory during VCF transformation"**
```bash
# Solution: Reduce batch size
python vcf_transform/vcf_to_beacon.py input.vcf.gz \
  --output variants.json \
  --batch-size 1000  # Smaller batches
```

**Issue: "Validation fails on large files"**
```bash
# Solution: Validate in chunks
split -l 10000 variants.json chunk_
for file in chunk_*; do
  python validation/validate_json.py $file
done
```

### Performance Optimization

**Large VCF Files** (>10M variants):
- Use `--batch-size 50000`
- Use `--workers 8` (number of CPU cores)
- Use `--filter-pass-only` to reduce size
- Process chromosomes separately

**MongoDB Import**:
- Use batch size 10000-50000
- Disable validation for trusted data
- Create indexes after import, not during
- Use upsert only when necessary

**Memory Management**:
- Close file handles explicitly
- Process in streaming mode when possible
- Clear cache between batches
- Monitor with `htop` or `top`

---

## Support

**Issues**: [GitHub Issues](https://github.com/AfriGen-D/variant-checker-beacon/issues)

**Documentation**: [Project Documentation](../docs/)

**Contact**: beacon-support@example.org

---

**Tool Version**: 1.0
**Last Updated**: 2025-01-26
**Compatible with**: Beacon v2.0
