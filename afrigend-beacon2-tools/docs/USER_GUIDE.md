# User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [VCF Processing](#vcf-processing)
3. [Phenotype Processing](#phenotype-processing)
4. [Data Validation](#data-validation)
5. [Data Import/Export](#data-importexport)
6. [Workflow Automation](#workflow-automation)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)

## Getting Started

### Quick Start Example

Transform a VCF file to Beacon v2 format:

```bash
# 1. Transform VCF to Beacon v2 JSON
python vcf_transform/vcf_to_beacon.py sample.vcf --output ./output

# 2. Validate the output
python validation/validate_json.py ./output --schema-type variant

# 3. Import to MongoDB
python data_import/import_to_mongo.py ./output --db beacon_db
```

### Understanding the Data Flow

```
VCF/Phenotype Files → Transform → Validate → Import → Query (Beacon API)
```

## VCF Processing

### Basic VCF Transformation

The VCF transformer converts genomic variant data into Beacon v2 compliant JSON format.

#### Simple Usage
```bash
python vcf_transform/vcf_to_beacon.py input.vcf --output ./output
```

#### With Metadata
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --output ./output \
    --metadata individuals.csv \
    --assembly GRCh38
```

#### Advanced Options
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --output ./output \
    --assembly GRCh38 \
    --metadata individuals.csv \
    --config config/settings.yaml \
    --min-qual 30 \
    --min-depth 20 \
    --max-missing 0.05 \
    --include-annotations \
    --batch-size 5000 \
    --verbose
```

### Input File Formats

#### VCF File Requirements
- **Format**: VCF 4.0+ compliant
- **Compression**: Supports .vcf, .vcf.gz, .bcf
- **Size**: No strict limits (tested up to 100GB+)
- **Samples**: Supports single or multi-sample VCFs

#### Metadata File Format (CSV/TSV)
```csv
individual_id,sex,population,age,disease_status
SAMPLE001,male,AFR,45,affected
SAMPLE002,female,AFR,32,unaffected
SAMPLE003,male,EUR,28,unknown
```

Required columns:
- `individual_id`: Must match VCF sample names
- `sex`: male/female/unknown
- `population`: Population code (AFR, EUR, EAS, SAS, AMR, etc.)

Optional columns:
- `age`: Age in years
- `disease_status`: affected/unaffected/unknown
- `ethnicity`: Detailed ethnicity information
- `consent_status`: Consent for data sharing

### Output Files

#### 1. variants_batch.jsonl
Genomic variants in Beacon v2 format (one JSON object per line):
```json
{
  "id": "variant_001",
  "assembly_id": "GRCh38",
  "reference_name": "chr1",
  "start": 100000,
  "end": 100001,
  "reference_bases": "A",
  "alternate_bases": "T",
  "variant_type": "SNV",
  "quality": 45.2,
  "filters": ["PASS"],
  "info": {
    "AF": 0.25,
    "AC": 10,
    "AN": 40
  }
}
```

#### 2. individuals.json
Individual/sample information:
```json
[
  {
    "id": "SAMPLE001",
    "sex": {"id": "NCIT:C20197", "label": "male"},
    "ethnicity": {"id": "HANCESTRO:0014", "label": "African"},
    "geographic_origin": {"id": "GAZ:00000001", "label": "Africa"},
    "karyotypic_sex": "XY",
    "age": {"age_class": {"id": "NCIT:C27954", "label": "Adult"}}
  }
]
```

#### 3. variant_genotypes.json
Variant-individual genotype associations:
```json
[
  {
    "variant_id": "variant_001",
    "individual_id": "SAMPLE001",
    "genotype": "0/1",
    "depth": 25,
    "quality": 42.3,
    "allelic_depths": [15, 10]
  }
]
```

### Quality Filtering

Configure quality filters in `config/settings.yaml`:

```yaml
vcf:
  quality_filters:
    min_qual: 20          # Minimum variant quality score
    min_depth: 10         # Minimum read depth
    max_missing_rate: 0.1 # Maximum missing genotype rate
    min_allele_count: 1   # Minimum allele count
    max_allele_freq: 0.99 # Maximum allele frequency
```

Apply filters during transformation:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --min-qual 30 \
    --min-depth 15 \
    --max-missing 0.05
```

### Annotation Handling

#### VEP Annotations
Extract Variant Effect Predictor annotations:
```bash
python vcf_transform/vcf_to_beacon.py annotated.vcf \
    --include-annotations \
    --annotation-type VEP
```

#### SnpEff Annotations
Extract SnpEff annotations:
```bash
python vcf_transform/vcf_to_beacon.py annotated.vcf \
    --include-annotations \
    --annotation-type SnpEff
```

## Phenotype Processing

### Basic Phenotype Transformation

Convert phenotype data to Beacon v2 format with ontology mapping.

#### Simple Usage
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv --output ./output
```

#### With Individual Mapping
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --output ./output \
    --individuals individuals.json
```

### Input File Formats

#### CSV/TSV Format
```csv
individual_id,phenotype_id,phenotype_label,onset_age,severity,evidence
SAMPLE001,HP:0001250,Seizures,5,severe,clinical_observation
SAMPLE001,HP:0001263,Global developmental delay,2,moderate,clinical_observation
SAMPLE002,MONDO:0007739,Huntington disease,45,severe,genetic_testing
```

Required columns:
- `individual_id`: Links to genomic data
- `phenotype_id`: HPO, MONDO, ORDO, or NCIT ID
- `phenotype_label`: Human-readable description

Optional columns:
- `onset_age`: Age of onset (years)
- `severity`: mild/moderate/severe
- `evidence`: Type of evidence
- `status`: observed/excluded
- `modifier`: Additional phenotype modifiers

#### Excel Format (.xlsx)
Supports multiple sheets:
- `phenotypes`: Main phenotype data
- `diseases`: Disease information
- `metadata`: Additional metadata

#### JSON Format
```json
[
  {
    "individual_id": "SAMPLE001",
    "phenotypes": [
      {
        "phenotype_id": "HP:0001250",
        "phenotype_label": "Seizures",
        "onset": {"age": 5},
        "severity": "severe",
        "evidence": "clinical_observation"
      }
    ]
  }
]
```

### Ontology Mapping

#### Automatic Ontology Resolution
The tool automatically maps phenotype IDs to ontologies:

```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --auto-map-ontologies \
    --ontology-cache ./cache
```

#### Manual Ontology Specification
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --ontology HPO \
    --ontology-file hpo.obo
```

#### Supported Ontologies
- **HPO**: Human Phenotype Ontology
- **MONDO**: Monarch Disease Ontology
- **ORDO**: Orphanet Rare Disease Ontology
- **NCIT**: NCI Thesaurus
- **SNOMED**: SNOMED Clinical Terms

### Output Files

#### 1. phenotypes.json
```json
[
  {
    "id": "phenotype_001",
    "phenotypic_feature": {
      "feature_type": {
        "id": "HP:0001250",
        "label": "Seizures"
      },
      "severity": {
        "id": "HP:0012828",
        "label": "Severe"
      },
      "onset": {
        "age": {"years": 5}
      },
      "evidence": {
        "evidence_code": {
          "id": "ECO:0000033",
          "label": "clinical observation"
        }
      }
    },
    "individual_id": "SAMPLE001"
  }
]
```

#### 2. diseases.json
```json
[
  {
    "id": "disease_001",
    "disease_code": {
      "id": "MONDO:0007739",
      "label": "Huntington disease"
    },
    "age_of_onset": {
      "age": {"years": 45}
    },
    "stage": {
      "id": "NCIT:C28108",
      "label": "Stage III"
    },
    "individual_id": "SAMPLE002"
  }
]
```

## Data Validation

### Schema Validation

#### Built-in Schemas
```bash
# Validate variants
python validation/validate_json.py variants.json --schema-type variant

# Validate individuals
python validation/validate_json.py individuals.json --schema-type individual

# Validate phenotypes
python validation/validate_json.py phenotypes.json --schema-type phenotype
```

#### Directory Validation
```bash
python validation/validate_json.py ./output --schema-type variant
```

#### Custom Schema
```bash
python validation/validate_json.py data.json --schema custom_schema.json
```

### Validation Modes

#### Strict Mode
Fails on any validation error:
```bash
python validation/validate_json.py data.json --strict
```

#### Lenient Mode (Default)
Reports errors but continues processing:
```bash
python validation/validate_json.py data.json --lenient
```

### Validation Output

#### Console Output
```
Validating: variants.json
✓ Schema validation passed
✓ 1,234 records validated
⚠ 5 warnings found:
  - Record 45: Unusual chromosome name: 'chr23'
  - Record 102: High allele frequency: 0.95

Summary:
  Files processed: 1
  Records validated: 1,234
  Errors: 0
  Warnings: 5
  Validation time: 2.3s
```

#### JSON Report
```bash
python validation/validate_json.py data.json --report validation_report.json
```

## Data Import/Export

### MongoDB Import

#### Single File Import
```bash
python data_import/import_to_mongo.py variants.json \
    --db beacon_db \
    --collection variants
```

#### Directory Import
```bash
python data_import/import_to_mongo.py ./output \
    --db beacon_db \
    --auto-detect-collections
```

#### Batch Import with Options
```bash
python data_import/import_to_mongo.py ./output \
    --db beacon_db \
    --batch-size 5000 \
    --upsert \
    --create-indexes \
    --validate-before-import
```

### MongoDB Export

#### Collection Export
```bash
python data_export/export_from_mongo.py \
    --db beacon_db \
    --collection variants \
    --output exported_variants.json
```

#### Filtered Export
```bash
python data_export/export_from_mongo.py \
    --db beacon_db \
    --collection variants \
    --query '{"assembly_id": "GRCh38", "variant_type": "SNV"}' \
    --output snvs_grch38.json
```

#### Aggregation Export
```bash
python data_export/export_from_mongo.py \
    --db beacon_db \
    --collection variants \
    --aggregation '[
      {"$group": {"_id": "$reference_name", "count": {"$sum": 1}}},
      {"$sort": {"count": -1}}
    ]' \
    --output variant_counts_by_chromosome.json
```

## Workflow Automation

### VCF to MongoDB Pipeline

#### Basic Pipeline
```bash
./examples/vcf_to_mongo_workflow.sh input.vcf
```

#### With Metadata
```bash
./examples/vcf_to_mongo_workflow.sh input.vcf \
    --metadata individuals.csv \
    --output ./processing
```

#### Advanced Pipeline
```bash
./examples/vcf_to_mongo_workflow.sh input.vcf \
    --metadata individuals.csv \
    --output ./processing \
    --assembly GRCh38 \
    --min-qual 30 \
    --validate-strict \
    --import-db beacon_production \
    --create-indexes \
    --cleanup
```

### Phenotype to MongoDB Pipeline

```bash
./examples/phenotype_to_mongo_workflow.sh phenotypes.csv \
    --individuals individuals.json \
    --output ./processing \
    --ontology HPO \
    --import-db beacon_db
```

### Custom Workflows

Create custom workflows by combining tools:

```bash
#!/bin/bash
# custom_workflow.sh

# 1. Transform VCF
python vcf_transform/vcf_to_beacon.py $1 --output ./temp

# 2. Transform phenotypes
python phenotype_transform/phenotype_to_beacon.py $2 --output ./temp

# 3. Validate all data
python validation/validate_json.py ./temp --schema-type variant

# 4. Import to MongoDB
python data_import/import_to_mongo.py ./temp --db beacon_db

# 5. Create summary report
python scripts/generate_summary.py --db beacon_db --output summary.html
```

## Advanced Usage

### Performance Optimization

#### Large File Processing
```yaml
# config/settings.yaml
processing:
  batch_size: 10000
  max_workers: 8
  memory_limit: 8192
  use_parallel_processing: true
```

#### Memory Management
```bash
python vcf_transform/vcf_to_beacon.py large_file.vcf \
    --batch-size 1000 \
    --memory-efficient \
    --temp-dir /fast/storage/temp
```

### Custom Annotations

#### Add Custom Fields
```python
# custom_transform.py
from vcf_transform.vcf_to_beacon import VCFTransformer

class CustomVCFTransformer(VCFTransformer):
    def add_custom_annotations(self, variant_record, vcf_record):
        # Add custom fields
        variant_record['custom_score'] = self.calculate_custom_score(vcf_record)
        variant_record['pathogenicity'] = self.predict_pathogenicity(vcf_record)
        return variant_record
```

#### Custom Ontology Mapping
```python
# custom_phenotype.py
from phenotype_transform.phenotype_to_beacon import PhenotypeTransformer

class CustomPhenotypeTransformer(PhenotypeTransformer):
    def map_custom_ontology(self, phenotype_id):
        # Custom ontology mapping logic
        return self.custom_ontology_db.get(phenotype_id)
```

### Integration with External Services

#### OMIM Integration
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --omim-api-key YOUR_API_KEY \
    --include-omim-data
```

#### ClinVar Integration
```bash
python vcf_transform/vcf_to_beacon.py variants.vcf \
    --clinvar-database clinvar.vcf.gz \
    --include-clinical-significance
```

## Best Practices

### Data Quality

1. **Validate Input Data**
   ```bash
   # Check VCF format
   bcftools view -h input.vcf | head -20
   
   # Validate VCF
   vcf-validator input.vcf
   ```

2. **Use Appropriate Quality Filters**
   ```yaml
   vcf:
     quality_filters:
       min_qual: 30      # Conservative for clinical data
       min_depth: 20     # Adequate coverage
       max_missing_rate: 0.05  # Strict for population studies
   ```

3. **Consistent Metadata**
   - Use standardized population codes
   - Validate individual IDs match between files
   - Include consent and sharing permissions

### Performance

1. **Optimize Batch Sizes**
   - Small files: batch_size = 1000
   - Large files: batch_size = 10000
   - Memory-constrained: batch_size = 500

2. **Use Parallel Processing**
   ```yaml
   processing:
     max_workers: 4  # Number of CPU cores
     parallel_collections: true
   ```

3. **Monitor Resource Usage**
   ```bash
   # Monitor during processing
   htop
   iotop
   df -h
   ```

### Data Security

1. **Secure MongoDB**
   ```yaml
   mongodb:
     username: "beacon_user"
     password: "strong_password"
     auth_source: "admin"
     ssl: true
   ```

2. **Encrypt Sensitive Data**
   ```bash
   # Encrypt files before processing
   gpg --encrypt --recipient user@example.com sensitive_data.vcf
   ```

3. **Access Control**
   - Implement proper user authentication
   - Use role-based access control
   - Audit data access logs

### Documentation

1. **Document Processing Parameters**
   ```yaml
   # processing_log.yaml
   processing_date: "2024-01-15"
   input_files:
     - "cohort_2024_variants.vcf"
     - "cohort_2024_phenotypes.csv"
   parameters:
     assembly: "GRCh38"
     min_qual: 30
     batch_size: 5000
   ```

2. **Maintain Data Provenance**
   - Record data sources
   - Document transformation steps
   - Version control configurations

3. **Create Processing Reports**
   ```bash
   python scripts/generate_processing_report.py \
     --input-log processing_log.yaml \
     --output processing_report.html
   ```

## Troubleshooting

### Common Issues

1. **Memory Errors**
   ```bash
   # Reduce batch size
   python vcf_transform/vcf_to_beacon.py input.vcf --batch-size 500
   ```

2. **MongoDB Connection Issues**
   ```bash
   # Test connection
   mongosh "mongodb://localhost:27017/beacon_db"
   ```

3. **Validation Failures**
   ```bash
   # Use lenient mode to identify issues
   python validation/validate_json.py data.json --lenient --verbose
   ```

For more troubleshooting guidance, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md). 