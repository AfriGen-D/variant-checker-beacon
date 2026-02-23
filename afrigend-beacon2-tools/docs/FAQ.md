# Frequently Asked Questions (FAQ)

## General Questions

### Q1: What is the AfriGend Beacon v2 Tools?
**A:** The AfriGend Beacon v2 Tools is a comprehensive toolkit for transforming genomic and phenotypic data into Beacon v2 compliant format. It includes tools for VCF transformation, phenotype processing, data validation, and MongoDB operations.

### Q2: What file formats are supported?
**A:** 
- **VCF files**: .vcf, .vcf.gz, .bcf
- **Phenotype files**: .csv, .tsv, .xlsx, .json
- **Metadata files**: .csv, .tsv
- **Output formats**: JSON, JSONL, CSV, TSV

### Q3: What are the system requirements?
**A:**
- Python 3.8 or higher
- 4GB+ RAM (8GB+ recommended for large datasets)
- MongoDB 4.4+ (for import/export operations)
- 10GB+ free disk space for processing

### Q4: Is the toolkit compatible with different genome assemblies?
**A:** Yes, it supports GRCh37, GRCh38, hg19, and hg38 assemblies. The default is GRCh38.

## Installation Questions

### Q5: How do I install the toolkit?
**A:** 
```bash
cd afrigend-beacon2-tools
pip install -r requirements.txt
```
See [INSTALLATION.md](INSTALLATION.md) for detailed instructions.

### Q6: I'm getting installation errors for pysam/cyvcf2. What should I do?
**A:** Install system dependencies first:
```bash
sudo apt-get install build-essential python3-dev zlib1g-dev libbz2-dev liblzma-dev
pip install pysam --no-binary pysam
pip install cyvcf2 --no-binary cyvcf2
```

### Q7: Can I use Docker instead of local installation?
**A:** Yes, Docker support is planned. Currently, use local installation with virtual environments.

## VCF Processing Questions

### Q8: What VCF versions are supported?
**A:** VCF 4.0 and later versions are supported. The toolkit handles both single-sample and multi-sample VCF files.

### Q9: How large VCF files can I process?
**A:** There's no strict size limit. Files up to 100GB+ have been tested successfully. For very large files, adjust batch size and memory settings.

### Q10: Can I filter variants during transformation?
**A:** Yes, you can apply quality filters:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --min-qual 30 \
    --min-depth 20 \
    --max-missing 0.05
```

### Q11: How do I handle VCF files with annotations (VEP/SnpEff)?
**A:** Use the `--include-annotations` flag:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --include-annotations \
    --annotation-type VEP
```

### Q12: What if my VCF doesn't have sample metadata?
**A:** You can provide a separate metadata file:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --metadata individuals.csv
```

## Phenotype Processing Questions

### Q13: What ontologies are supported?
**A:** HPO (Human Phenotype Ontology), MONDO, ORDO, NCIT, and SNOMED CT.

### Q14: How do I map custom phenotype terms?
**A:** The toolkit can auto-map terms or you can provide ontology files:
```bash
python phenotype_transform/phenotype_to_beacon.py phenotypes.csv \
    --auto-map-ontologies \
    --ontology-file hp.obo
```

### Q15: Can I process Excel files with multiple sheets?
**A:** Yes, the toolkit supports Excel files with multiple sheets for different data types.

### Q16: What if I have phenotype data in a custom format?
**A:** Convert to CSV/TSV with required columns: individual_id, phenotype_id, phenotype_label. See [USER_GUIDE.md](USER_GUIDE.md) for details.

## Data Validation Questions

### Q17: How do I validate my transformed data?
**A:** Use the validation tool:
```bash
python validation/validate_json.py ./output --schema-type variant
```

### Q18: What if validation fails?
**A:** Use lenient mode to identify issues:
```bash
python validation/validate_json.py data.json --lenient --verbose
```

### Q19: Can I use custom validation schemas?
**A:** Yes, provide your own schema file:
```bash
python validation/validate_json.py data.json --schema custom_schema.json
```

## MongoDB Questions

### Q20: Do I need MongoDB installed locally?
**A:** Only if you want to use import/export features. You can also use MongoDB Atlas (cloud).

### Q21: How do I connect to MongoDB Atlas?
**A:** Update your configuration with the Atlas connection string:
```yaml
mongodb:
  uri: "mongodb+srv://username:password@cluster.mongodb.net/beacon_db"
```

### Q22: Can I import data without validation?
**A:** Yes, but validation is recommended:
```bash
python data_import/import_to_mongo.py data.json \
    --db beacon_db \
    --skip-validation
```

### Q23: How do I handle large datasets for MongoDB import?
**A:** Increase batch size and use bulk operations:
```bash
python data_import/import_to_mongo.py data.json \
    --batch-size 10000 \
    --bulk-operations
```

## Performance Questions

### Q24: How can I speed up processing?
**A:** 
- Increase batch size: `--batch-size 5000`
- Use more workers: adjust `max_workers` in config
- Use faster storage for temp files
- Allocate more memory: adjust `memory_limit` in config

### Q25: My process is running out of memory. What should I do?
**A:** 
- Reduce batch size: `--batch-size 500`
- Reduce max workers in configuration
- Use streaming mode for very large files

### Q26: Can I process files in parallel?
**A:** Yes, the toolkit supports parallel processing. Configure `max_workers` in `config/settings.yaml`.

## Configuration Questions

### Q27: Where is the configuration file?
**A:** `config/settings.yaml` - copy from `config/settings.yaml.example` if needed.

### Q28: Can I override configuration with environment variables?
**A:** Yes, use format `BEACON_SECTION_SETTING`:
```bash
export BEACON_MONGODB_HOST="production-server"
export BEACON_PROCESSING_BATCH_SIZE="5000"
```

### Q29: How do I configure for different environments?
**A:** Create environment-specific config files:
- `config/development.yaml`
- `config/production.yaml`
- `config/testing.yaml`

## Workflow Questions

### Q30: Can I automate the entire pipeline?
**A:** Yes, use the provided workflow scripts:
```bash
./examples/vcf_to_mongo_workflow.sh input.vcf
./examples/phenotype_to_mongo_workflow.sh phenotypes.csv
```

### Q31: How do I create custom workflows?
**A:** Combine individual tools in a bash script. See examples in the `examples/` directory.

### Q32: Can I skip certain steps in the workflow?
**A:** Yes, workflow scripts support skip options:
```bash
./examples/vcf_to_mongo_workflow.sh input.vcf --skip-validation
./examples/vcf_to_mongo_workflow.sh input.vcf --skip-import
```

## Data Quality Questions

### Q33: How do I check data quality before processing?
**A:** Use diagnostic tools:
```bash
python scripts/analyze_vcf.py input.vcf
python scripts/check_data_completeness.py input.vcf
```

### Q34: What if my data has inconsistencies?
**A:** Enable data cleaning:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --clean-data \
    --normalize-chromosomes
```

### Q35: How do I handle missing required fields?
**A:** Use field filling options:
```bash
python vcf_transform/vcf_to_beacon.py input.vcf \
    --fill-missing-fields
```

## Integration Questions

### Q36: Can I integrate with existing Beacon APIs?
**A:** Yes, the output is fully Beacon v2 compliant and can be used with any Beacon v2 implementation.

### Q37: How do I connect to external ontology services?
**A:** Configure URLs in `config/settings.yaml`:
```yaml
data_sources:
  ontologies:
    hpo_url: "https://hpo.jax.org/api/hpo/term/"
```

### Q38: Can I use custom annotation databases?
**A:** Yes, you can extend the toolkit to include custom annotation sources. See [API_REFERENCE.md](API_REFERENCE.md) for details.

## Troubleshooting Questions

### Q39: Where can I find error logs?
**A:** Enable logging in configuration:
```yaml
processing:
  log_level: "DEBUG"
  log_file: "beacon_transform.log"
```

### Q40: How do I report bugs or get support?
**A:** 
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Enable debug logging
3. Open an issue on GitHub with system info and error details

### Q41: Can I test the toolkit with sample data?
**A:** Yes, download sample data:
```bash
python scripts/download_sample_data.py
python scripts/test_with_samples.py
```

## Advanced Usage Questions

### Q42: Can I extend the toolkit with custom transformations?
**A:** Yes, create custom transformer classes. See [API_REFERENCE.md](API_REFERENCE.md) for examples.

### Q43: How do I add support for new ontologies?
**A:** Extend the ontology mapping classes and update configuration:
```python
class CustomOntologyMapper(OntologyMapper):
    def map_custom_ontology(self, term_id):
        # Custom mapping logic
        pass
```

### Q44: Can I process data in streaming mode?
**A:** Yes, enable streaming mode for very large files:
```yaml
processing:
  streaming_mode: true
  batch_size: 1000
```

### Q45: How do I create custom validation rules?
**A:** Extend the validator class:
```python
class CustomValidator(BeaconValidator):
    def validate_custom_rules(self, data):
        # Custom validation logic
        pass
```

## Security Questions

### Q46: How do I secure MongoDB connections?
**A:** Use authentication and SSL:
```yaml
mongodb:
  username: "beacon_user"
  password: "secure_password"
  ssl: true
  auth_source: "admin"
```

### Q47: Can I encrypt sensitive data?
**A:** Yes, encrypt files before processing:
```bash
gpg --encrypt --recipient user@example.com sensitive_data.vcf
```

### Q48: How do I implement access controls?
**A:** Use MongoDB's role-based access control and implement authentication in your application layer.

## Licensing and Usage Questions

### Q49: What license is the toolkit released under?
**A:** [Check the LICENSE file in the repository for current licensing terms]

### Q50: Can I use this toolkit for commercial purposes?
**A:** [Refer to the LICENSE file for commercial usage terms]

### Q51: How do I cite this toolkit in publications?
**A:** [Citation information will be provided in the main README]

## Getting More Help

If your question isn't answered here:

1. **Check the documentation**:
   - [USER_GUIDE.md](USER_GUIDE.md) - Comprehensive usage guide
   - [INSTALLATION.md](INSTALLATION.md) - Installation instructions
   - [CONFIGURATION.md](CONFIGURATION.md) - Configuration details
   - [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

2. **Use diagnostic tools**:
   ```bash
   python scripts/system_info.py
   python scripts/check_environment.py
   ```

3. **Enable debug logging**:
   ```yaml
   processing:
     log_level: "DEBUG"
   ```

4. **Open an issue on GitHub** with:
   - System information
   - Complete error messages
   - Steps to reproduce
   - Sample data (if possible)

5. **Contact the development team** for specific questions about implementation or integration. 