# Installation Guide

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows (with WSL recommended)
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 4GB RAM (8GB+ recommended for large datasets)
- **Storage**: 10GB+ free space for processing large VCF files
- **MongoDB**: Version 4.4+ (for data import/export operations)

### Python Dependencies

The toolkit requires several specialized bioinformatics and data processing libraries:

#### Core Dependencies
- `pysam>=0.19.0` - SAM/BAM/VCF file manipulation
- `cyvcf2>=0.30.0` - Fast VCF parsing
- `pandas>=1.3.0` - Data manipulation and analysis
- `numpy>=1.21.0` - Numerical computing
- `pymongo>=4.0.0` - MongoDB driver
- `jsonschema>=4.0.0` - JSON schema validation

#### Bioinformatics Libraries
- `pronto>=2.4.0` - Ontology processing (HPO, MONDO, etc.)
- `bioservices>=1.8.0` - Access to biological web services
- `biopython>=1.79` - Biological computation

#### Data Processing
- `openpyxl>=3.0.0` - Excel file support
- `xlrd>=2.0.0` - Excel file reading
- `tqdm>=4.62.0` - Progress bars
- `click>=8.0.0` - Command-line interface

## Installation Methods

### Method 1: Standard Installation (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/afrigend-beacon2.git
   cd afrigend-beacon2/afrigend-beacon2-tools
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify installation**:
   ```bash
   python vcf_transform/vcf_to_beacon.py --help
   python phenotype_transform/phenotype_to_beacon.py --help
   python validation/validate_json.py --help
   ```

### Method 2: Development Installation

For development and testing:

1. **Install in editable mode**:
   ```bash
   pip install -e .
   ```

2. **Install development dependencies**:
   ```bash
   pip install pytest pytest-cov black flake8 mypy
   ```

3. **Run tests**:
   ```bash
   python -m pytest tests/ -v
   ```

### Method 3: Docker Installation

Using Docker for containerized deployment:

1. **Build Docker image**:
   ```bash
   docker build -t afrigend-beacon2-tools .
   ```

2. **Run container**:
   ```bash
   docker run -v $(pwd)/data:/data afrigend-beacon2-tools \
     python vcf_transform/vcf_to_beacon.py /data/input.vcf --output /data/output
   ```

## MongoDB Setup

### Local MongoDB Installation

#### Ubuntu/Debian:
```bash
wget -qO - https://www.mongodb.org/static/pgp/server-5.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/5.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-5.0.list
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### macOS (using Homebrew):
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb/brew/mongodb-community
```

#### Windows:
Download and install from [MongoDB Download Center](https://www.mongodb.com/try/download/community)

### MongoDB Configuration

1. **Create database and user**:
   ```javascript
   // Connect to MongoDB shell
   mongosh

   // Create database
   use beacon_db

   // Create user with read/write permissions
   db.createUser({
     user: "beacon_user",
     pwd: "secure_password",
     roles: [
       { role: "readWrite", db: "beacon_db" }
     ]
   })
   ```

2. **Update configuration**:
   Edit `config/settings.yaml`:
   ```yaml
   mongodb:
     host: "localhost"
     port: 27017
     database: "beacon_db"
     username: "beacon_user"
     password: "secure_password"
   ```

### Cloud MongoDB (MongoDB Atlas)

1. **Create cluster** at [MongoDB Atlas](https://cloud.mongodb.com/)

2. **Get connection string**:
   ```
   mongodb+srv://username:password@cluster.mongodb.net/beacon_db
   ```

3. **Update configuration**:
   ```yaml
   mongodb:
     uri: "mongodb+srv://username:password@cluster.mongodb.net/beacon_db"
   ```

## Configuration

### Basic Configuration

Copy and customize the configuration file:

```bash
cp config/settings.yaml.example config/settings.yaml
```

Key configuration sections:

#### MongoDB Settings
```yaml
mongodb:
  host: "localhost"
  port: 27017
  database: "beacon_db"
  connection_timeout: 30
```

#### Processing Settings
```yaml
processing:
  batch_size: 1000        # Records per batch
  max_workers: 4          # Parallel processes
  memory_limit: 2048      # MB per process
  log_level: "INFO"       # DEBUG, INFO, WARNING, ERROR
```

#### VCF Processing
```yaml
vcf:
  default_assembly: "GRCh38"
  quality_filters:
    min_qual: 20
    min_depth: 10
    max_missing_rate: 0.1
```

### Advanced Configuration

#### Custom Ontology Sources
```yaml
data_sources:
  ontologies:
    custom_hpo_url: "https://your-server.com/hpo/"
    local_mondo_file: "/path/to/mondo.obo"
```

#### Performance Tuning
```yaml
processing:
  batch_size: 5000        # Larger batches for better performance
  max_workers: 8          # More workers for multi-core systems
  memory_limit: 4096      # More memory for large files
```

## Verification

### Test Installation

1. **Run basic tests**:
   ```bash
   python tests/test_tools.py
   ```

2. **Test with sample data**:
   ```bash
   # Download sample VCF
   wget https://github.com/samtools/hts-specs/raw/master/test/tabix/example.vcf

   # Test VCF transformation
   python vcf_transform/vcf_to_beacon.py example.vcf --output ./test_output

   # Validate output
   python validation/validate_json.py ./test_output --schema-type variant
   ```

3. **Test MongoDB connection**:
   ```bash
   python -c "
   from pymongo import MongoClient
   import yaml
   
   with open('config/settings.yaml') as f:
       config = yaml.safe_load(f)
   
   client = MongoClient(config['mongodb']['host'], config['mongodb']['port'])
   db = client[config['mongodb']['database']]
   print('MongoDB connection successful!')
   print(f'Available collections: {db.list_collection_names()}')
   "
   ```

## Troubleshooting

### Common Issues

#### 1. Python Version Errors
```bash
# Check Python version
python --version

# Use specific Python version
python3.8 -m venv venv
```

#### 2. Dependency Installation Failures
```bash
# Update pip and setuptools
pip install --upgrade pip setuptools wheel

# Install with verbose output
pip install -r requirements.txt -v

# Install problematic packages individually
pip install pysam --no-binary pysam
```

#### 3. MongoDB Connection Issues
```bash
# Check MongoDB status
sudo systemctl status mongod

# Check connection
mongosh --eval "db.adminCommand('ismaster')"

# Check firewall
sudo ufw allow 27017
```

#### 4. Memory Issues with Large Files
```yaml
# Reduce batch size in config/settings.yaml
processing:
  batch_size: 500
  memory_limit: 1024
```

#### 5. Permission Issues
```bash
# Fix file permissions
chmod +x examples/*.sh
chmod -R 755 afrigend-beacon2-tools/
```

### Performance Optimization

#### For Large VCF Files (>1GB)
```yaml
processing:
  batch_size: 10000
  max_workers: 8
  memory_limit: 8192

vcf:
  quality_filters:
    min_qual: 30          # Stricter filtering
    min_depth: 20
```

#### For High-Throughput Processing
```yaml
mongodb:
  connection_pool_size: 20
  max_idle_time_ms: 30000

processing:
  parallel_collections: true
  async_operations: true
```

## Next Steps

After successful installation:

1. **Read the User Guide**: `docs/USER_GUIDE.md`
2. **Explore Examples**: `examples/`
3. **Review Configuration**: `docs/CONFIGURATION.md`
4. **Check API Reference**: `docs/API_REFERENCE.md`

## Support

For installation issues:
- Check the [FAQ](docs/FAQ.md)
- Review [troubleshooting](docs/TROUBLESHOOTING.md)
- Open an issue on GitHub
- Contact the development team 