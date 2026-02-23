#!/bin/bash

# AfriGend Beacon v2 - Phenotype to MongoDB Workflow Example
# This script demonstrates a complete pipeline from phenotype transformation to MongoDB import

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$TOOLS_DIR/config/settings.yaml"

# Default values
INPUT_PHENOTYPE=""
INDIVIDUALS_FILE=""
OUTPUT_DIR="./phenotype_output"
DB_NAME="beacon_db"
MONGO_URI="mongodb://localhost:27017/"
VALIDATE_ONLY=false
SKIP_TRANSFORM=false
SKIP_VALIDATE=false
SKIP_IMPORT=false

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] <input_phenotype>

AfriGend Beacon v2 - Phenotype to MongoDB Workflow

Required:
  <input_phenotype>        Path to input phenotype file (CSV/TSV/XLSX/JSON)

Options:
  -i, --individuals FILE   Path to individuals JSON file to update
  -o, --output DIR         Output directory (default: ./phenotype_output)
  -d, --db NAME            MongoDB database name (default: beacon_db)
  -u, --mongo-uri URI      MongoDB connection URI (default: mongodb://localhost:27017/)
  -c, --config FILE        Configuration file path
  --validate-only          Only validate existing output files
  --skip-transform         Skip phenotype transformation step
  --skip-validate          Skip validation step
  --skip-import            Skip MongoDB import step
  -h, --help               Show this help message

Examples:
  # Complete workflow
  $0 phenotypes.csv -i individuals.json -o ./output

  # Validate only
  $0 phenotypes.csv --validate-only

  # Skip transformation (use existing output)
  $0 phenotypes.csv --skip-transform

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--individuals)
            INDIVIDUALS_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -d|--db)
            DB_NAME="$2"
            shift 2
            ;;
        -u|--mongo-uri)
            MONGO_URI="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --skip-transform)
            SKIP_TRANSFORM=true
            shift
            ;;
        --skip-validate)
            SKIP_VALIDATE=true
            shift
            ;;
        --skip-import)
            SKIP_IMPORT=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$INPUT_PHENOTYPE" ]]; then
                INPUT_PHENOTYPE="$1"
            else
                error "Multiple input files specified"
                exit 1
            fi
            shift
            ;;
    esac
done

# Check required arguments
if [[ -z "$INPUT_PHENOTYPE" ]]; then
    error "Input phenotype file is required"
    show_usage
    exit 1
fi

# Check if input file exists
if [[ ! -f "$INPUT_PHENOTYPE" ]]; then
    error "Input phenotype file not found: $INPUT_PHENOTYPE"
    exit 1
fi

# Check if individuals file exists (if provided)
if [[ -n "$INDIVIDUALS_FILE" && ! -f "$INDIVIDUALS_FILE" ]]; then
    error "Individuals file not found: $INDIVIDUALS_FILE"
    exit 1
fi

# Check if tools directory exists
if [[ ! -d "$TOOLS_DIR" ]]; then
    error "Tools directory not found: $TOOLS_DIR"
    exit 1
fi

# Check if required Python scripts exist
PHENOTYPE_TRANSFORM_SCRIPT="$TOOLS_DIR/phenotype_transform/phenotype_to_beacon.py"
VALIDATE_SCRIPT="$TOOLS_DIR/validation/validate_json.py"
IMPORT_SCRIPT="$TOOLS_DIR/data_import/import_to_mongo.py"

if [[ ! -f "$PHENOTYPE_TRANSFORM_SCRIPT" ]]; then
    error "Phenotype transformation script not found: $PHENOTYPE_TRANSFORM_SCRIPT"
    exit 1
fi

if [[ ! -f "$VALIDATE_SCRIPT" ]]; then
    error "Validation script not found: $VALIDATE_SCRIPT"
    exit 1
fi

if [[ ! -f "$IMPORT_SCRIPT" ]]; then
    error "Import script not found: $IMPORT_SCRIPT"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

log "Starting AfriGend Beacon v2 Phenotype to MongoDB workflow"
log "Input phenotype: $INPUT_PHENOTYPE"
log "Output directory: $OUTPUT_DIR"
log "Database: $DB_NAME"

# Step 1: Phenotype Transformation
if [[ "$SKIP_TRANSFORM" == false && "$VALIDATE_ONLY" == false ]]; then
    log "Step 1: Transforming phenotype data to Beacon v2 format"
    
    # Build transformation command
    TRANSFORM_CMD="python $PHENOTYPE_TRANSFORM_SCRIPT"
    TRANSFORM_CMD="$TRANSFORM_CMD $INPUT_PHENOTYPE"
    TRANSFORM_CMD="$TRANSFORM_CMD --output $OUTPUT_DIR"
    TRANSFORM_CMD="$TRANSFORM_CMD --config $CONFIG_FILE"
    TRANSFORM_CMD="$TRANSFORM_CMD --verbose"
    
    if [[ -n "$INDIVIDUALS_FILE" ]]; then
        TRANSFORM_CMD="$TRANSFORM_CMD --individuals $INDIVIDUALS_FILE"
    fi
    
    info "Running: $TRANSFORM_CMD"
    
    if eval "$TRANSFORM_CMD"; then
        log "Phenotype transformation completed successfully"
    else
        error "Phenotype transformation failed"
        exit 1
    fi
else
    if [[ "$VALIDATE_ONLY" == true ]]; then
        log "Skipping phenotype transformation (validate-only mode)"
    else
        log "Skipping phenotype transformation (--skip-transform)"
    fi
fi

# Step 2: Validation
if [[ "$SKIP_VALIDATE" == false ]]; then
    log "Step 2: Validating transformed data"
    
    # Check if output files exist
    if [[ ! -d "$OUTPUT_DIR" ]]; then
        error "Output directory not found: $OUTPUT_DIR"
        exit 1
    fi
    
    # Validate each output file
    VALIDATION_FAILED=false
    
    # Validate phenotypes
    if [[ -f "$OUTPUT_DIR/phenotypes.json" ]]; then
        info "Validating phenotypes..."
        if python "$VALIDATE_SCRIPT" "$OUTPUT_DIR/phenotypes.json" --schema-type phenotype --strict; then
            log "Phenotypes validation passed"
        else
            error "Phenotypes validation failed"
            VALIDATION_FAILED=true
        fi
    else
        warn "Phenotypes file not found: $OUTPUT_DIR/phenotypes.json"
    fi
    
    # Validate diseases
    if [[ -f "$OUTPUT_DIR/diseases.json" ]]; then
        info "Validating diseases..."
        if python "$VALIDATE_SCRIPT" "$OUTPUT_DIR/diseases.json" --schema-type phenotype --strict; then
            log "Diseases validation passed"
        else
            error "Diseases validation failed"
            VALIDATION_FAILED=true
        fi
    else
        warn "Diseases file not found: $OUTPUT_DIR/diseases.json"
    fi
    
    # Validate updated individuals (if created)
    if [[ -f "$OUTPUT_DIR/individuals_with_phenotypes.json" ]]; then
        info "Validating updated individuals..."
        if python "$VALIDATE_SCRIPT" "$OUTPUT_DIR/individuals_with_phenotypes.json" --schema-type individual --strict; then
            log "Updated individuals validation passed"
        else
            error "Updated individuals validation failed"
            VALIDATION_FAILED=true
        fi
    else
        warn "Updated individuals file not found: $OUTPUT_DIR/individuals_with_phenotypes.json"
    fi
    
    if [[ "$VALIDATION_FAILED" == true ]]; then
        error "Validation failed - stopping workflow"
        exit 1
    fi
    
    log "All validations passed"
else
    log "Skipping validation (--skip-validate)"
fi

# Step 3: MongoDB Import
if [[ "$SKIP_IMPORT" == false && "$VALIDATE_ONLY" == false ]]; then
    log "Step 3: Importing data to MongoDB"
    
    # Test MongoDB connection
    info "Testing MongoDB connection..."
    if python -c "
import pymongo
try:
    client = pymongo.MongoClient('$MONGO_URI', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print('MongoDB connection successful')
    client.close()
except Exception as e:
    print(f'MongoDB connection failed: {e}')
    exit(1)
"; then
        log "MongoDB connection successful"
    else
        error "MongoDB connection failed"
        exit 1
    fi
    
    # Import phenotypes
    if [[ -f "$OUTPUT_DIR/phenotypes.json" ]]; then
        info "Importing phenotypes to MongoDB..."
        if python "$IMPORT_SCRIPT" "$OUTPUT_DIR/phenotypes.json" --db "$DB_NAME" --collection phenotypes --mongo-uri "$MONGO_URI" --verbose; then
            log "Phenotypes imported successfully"
        else
            error "Phenotypes import failed"
            exit 1
        fi
    fi
    
    # Import diseases
    if [[ -f "$OUTPUT_DIR/diseases.json" ]]; then
        info "Importing diseases to MongoDB..."
        if python "$IMPORT_SCRIPT" "$OUTPUT_DIR/diseases.json" --db "$DB_NAME" --collection diseases --mongo-uri "$MONGO_URI" --verbose; then
            log "Diseases imported successfully"
        else
            error "Diseases import failed"
            exit 1
        fi
    fi
    
    # Import updated individuals (if created)
    if [[ -f "$OUTPUT_DIR/individuals_with_phenotypes.json" ]]; then
        info "Importing updated individuals to MongoDB..."
        if python "$IMPORT_SCRIPT" "$OUTPUT_DIR/individuals_with_phenotypes.json" --db "$DB_NAME" --collection individuals --mongo-uri "$MONGO_URI" --verbose; then
            log "Updated individuals imported successfully"
        else
            error "Updated individuals import failed"
            exit 1
        fi
    fi
    
    log "All data imported to MongoDB successfully"
else
    if [[ "$VALIDATE_ONLY" == true ]]; then
        log "Skipping MongoDB import (validate-only mode)"
    else
        log "Skipping MongoDB import (--skip-import)"
    fi
fi

# Summary
log "Workflow completed successfully!"
log "Output files:"
if [[ -d "$OUTPUT_DIR" ]]; then
    ls -la "$OUTPUT_DIR"
fi

if [[ "$SKIP_IMPORT" == false && "$VALIDATE_ONLY" == false ]]; then
    log "Data imported to MongoDB database: $DB_NAME"
    log "Collections created: phenotypes, diseases, individuals (updated)"
fi

log "Workflow completed at $(date)" 