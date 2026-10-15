#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# AfriGend Beacon v2 — ILIFU Data Loading Pipeline
# Transforms VCF data → Beacon v2 JSON → Validates → Imports to MongoDB
#
# Prerequisites:
#   - Running on an ILIFU compute node (NOT the login node)
#   - SSH access to beacon server for MongoDB tunnel
#
# Usage:
#   ./scripts/run_ilifu_pipeline.sh <vcf_file> [options]
#
# Examples:
#   ./scripts/run_ilifu_pipeline.sh /cbio/dbs/refpanels/H3AR3b/merged.vcf.gz
#   ./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz --phenotypes /path/to/pheno.csv
#   ./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz --assembly GRCh37 --skip-import
# ──────────────────────────────────────────────────────────────────────────────

# --- Configuration ---
# Neither default is tied to one person or one clone directory name: the tools
# live next to this script's repository, and output goes under the caller's own
# ILIFU home. Override either with TOOLS_DIR / OUTPUT_DIR / --output.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="${TOOLS_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/afrigend-beacon2-tools}"
OUTPUT_DIR="${OUTPUT_DIR:-/cbio/users/${USER:-$(id -un)}/beacon_output}"
BEACON_HOST="${BEACON_HOST:-<your-ssh-alias>}"
MONGO_DB="${MONGO_DB:-beacon_db}"
ASSEMBLY="${ASSEMBLY:-GRCh38}"
# Written into every variant's dataset_ids. The API filters per-dataset results
# on this field, so a wrong or empty value makes every dataset answer "not
# found" and suppresses allele frequencies entirely. Must match the id in the
# datasets collection — production serves H3A_V6_AFR.
DATASET_ID="${DATASET_ID:-H3A_V6_AFR}"
TUNNEL_PORT="${TUNNEL_PORT:-27017}"

# --- Parse arguments ---
VCF_FILE=""
PHENOTYPE_FILE=""
SKIP_IMPORT=false
SKIP_VALIDATE=false
CONTAINER="${BEACON_CONTAINER:-}"
RUNTIME_PREF="${BEACON_RUNTIME:-auto}"
DRY_RUN=false
BATCH_SIZE=5000
MAX_WORKERS=4

usage() {
    cat <<'USAGE'
Usage: run_ilifu_pipeline.sh <vcf_file> [options]

Arguments:
  <vcf_file>                Path to input VCF file (.vcf.gz or .bcf)

Options:
  --phenotypes <file>       Path to phenotype data (CSV/TSV/XLSX)
  --assembly <id>           Genome assembly (default: GRCh38)
  --dataset-id <id>         Dataset to attribute variants to (default: H3A_V6_AFR).
                            Must match an id in the datasets collection, or the
                            API reports "not found" for every dataset.
  --output <dir>            Output directory (default: /cbio/users/$USER/beacon_output)
  --batch-size <n>          Processing batch size (default: 5000)
  --workers <n>             Parallel workers (default: 4)
  --container <image>       Run the tools from a container instead of a Python
                            environment: nothing to install. A .sif file or a
                            docker:// URI runs with Singularity/Apptainer (ILIFU);
                            a plain image name runs with Docker. Also set by
                            BEACON_CONTAINER.
  --runtime <name>          singularity, apptainer, docker or auto (default: auto,
                            chosen from the --container value). Also BEACON_RUNTIME.
                            Singularity binds /cbio and /scratch3; Docker mounts the
                            VCF, phenotype and output directories. Set CONTAINER_BIND
                            (comma-separated paths) to add more.
  --skip-import             Transform + validate only, don't import to MongoDB
  --skip-validate           Skip validation step
  --dry-run                 Show what would be done without executing
  -h, --help                Show this help message
USAGE
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phenotypes)   PHENOTYPE_FILE="$2"; shift 2 ;;
        --assembly)     ASSEMBLY="$2"; shift 2 ;;
        --dataset-id)   DATASET_ID="$2"; shift 2 ;;
        --output)       OUTPUT_DIR="$2"; shift 2 ;;
        --batch-size)   BATCH_SIZE="$2"; shift 2 ;;
        --workers)      MAX_WORKERS="$2"; shift 2 ;;
        --container)    CONTAINER="$2"; shift 2 ;;
        --runtime)      RUNTIME_PREF="$2"; shift 2 ;;
        --skip-import)  SKIP_IMPORT=true; shift ;;
        --skip-validate) SKIP_VALIDATE=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage ;;
        -*)             echo "Unknown option: $1" >&2; usage ;;
        *)              VCF_FILE="$1"; shift ;;
    esac
done

[[ -z "$VCF_FILE" ]] && { echo "Error: VCF file is required"; usage; }

# --- Helpers ---
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { log "ERROR: $*" >&2; exit 1; }
step() { echo; echo "━━━ Step $1: $2 ━━━"; }

# --- How the tools are run: from a container, or from a Python virtualenv ---
PY=(python)
if [[ -n "$CONTAINER" ]]; then
    # A container resolves relative paths against its own directory, so use
    # absolute ones everywhere.
    abspath() {
        ( cd "$(dirname "$1")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "$1")" ) \
            || printf '%s\n' "$1"
    }
    VCF_FILE="$(abspath "$VCF_FILE")"
    [[ -z "$PHENOTYPE_FILE" ]] || PHENOTYPE_FILE="$(abspath "$PHENOTYPE_FILE")"
    OUTPUT_DIR="$(abspath "$OUTPUT_DIR")"

    KIND="$RUNTIME_PREF"
    if [[ "$KIND" == auto ]]; then
        if [[ "$CONTAINER" == *.sif || "$CONTAINER" == docker://* ]]; then
            KIND=singularity
        else
            KIND=docker
        fi
    fi

    case "$KIND" in
        singularity|apptainer)
            RUNTIME="$(command -v apptainer || command -v singularity || true)"
            [[ -n "$RUNTIME" ]] || die "$KIND runtime requested but neither apptainer nor singularity is on this node"
            [[ "$CONTAINER" == docker://* || -f "$CONTAINER" ]] \
                || die "Container image not found: $CONTAINER (a .sif file or a docker:// URI)"
            PY=("$RUNTIME" exec --bind "${CONTAINER_BIND:-/cbio,/scratch3}" "$CONTAINER" python)
            ;;
        docker)
            command -v docker >/dev/null || die "docker runtime requested but the docker command is not on this machine"
            # Create the output directory as this user, or Docker creates it as root.
            mkdir -p "$OUTPUT_DIR"
            DOCKER_V=(-v "$OUTPUT_DIR:$OUTPUT_DIR")
            SEEN=" $OUTPUT_DIR "
            for d in "$(dirname "$VCF_FILE")" \
                     "${PHENOTYPE_FILE:+$(dirname "$PHENOTYPE_FILE")}" \
                     ${CONTAINER_BIND//,/ }; do
                [[ -n "$d" ]] || continue
                case "$SEEN" in
                    *" $d "*) ;;
                    *) SEEN="$SEEN$d "; DOCKER_V+=(-v "$d:$d") ;;
                esac
            done
            # Same paths inside and outside, run as this user, and the host network
            # so the SSH tunnel to MongoDB on localhost is reachable.
            PY=(docker run --rm --network host -u "$(id -u):$(id -g)" -e HOME=/tmp
                -w "$OUTPUT_DIR" "${DOCKER_V[@]}" --entrypoint= "$CONTAINER" python)
            ;;
        *)
            die "Unknown --runtime: $KIND (use singularity, apptainer, docker or auto)"
            ;;
    esac
    TOOLS_DIR=/opt/beacon-tools   # where the image keeps the tools
fi

# --- Pre-flight checks ---
log "AfriGend Beacon v2 — ILIFU Data Loading Pipeline"
log "VCF:       $VCF_FILE"
log "Assembly:  $ASSEMBLY"
log "Dataset:   $DATASET_ID"
log "Output:    $OUTPUT_DIR"
log "Phenotype: ${PHENOTYPE_FILE:-none}"
if [[ -n "$CONTAINER" ]]; then
    log "Tools:     container $CONTAINER ($KIND)"
else
    log "Tools:     $TOOLS_DIR"
fi
log "Batch:     $BATCH_SIZE, Workers: $MAX_WORKERS"

[[ -f "$VCF_FILE" ]] || die "VCF file not found: $VCF_FILE"
[[ -n "$CONTAINER" || -d "$TOOLS_DIR" ]] || die "Tools directory not found: $TOOLS_DIR"

if [[ -n "$PHENOTYPE_FILE" ]] && [[ ! -f "$PHENOTYPE_FILE" ]]; then
    die "Phenotype file not found: $PHENOTYPE_FILE"
fi

# Check we're on a compute node (not login)
HOSTNAME=$(hostname)
if [[ "$HOSTNAME" == *"login"* ]] || [[ "$HOSTNAME" == *"slurm-login"* ]]; then
    die "Running on login node ($HOSTNAME). Request a compute node first:
    srun --pty --nodes=1 --ntasks-per-node=1 --cpus-per-task=4 --mem=32G --time=7-0:0:0 --nodelist=compute-[205,209] bash"
fi

if [[ "$DRY_RUN" == true ]]; then
    log "[DRY RUN] Would execute pipeline with above settings"
    exit 0
fi

# --- Setup virtual environment ---
step 1 "Setting up Python environment"

VENV_DIR="$TOOLS_DIR/.venv"

if [[ -n "$CONTAINER" ]]; then
    log "Using container: $CONTAINER (nothing to install)"
elif [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip "setuptools<70" wheel
    # requirements-runtime.txt, wheels only: the full requirements.txt pins
    # numpy and cyvcf2 versions that have no Python 3.12 build, so it cannot be
    # installed on a current ILIFU node. See the header of that file.
    pip install --only-binary=:all: -r "$TOOLS_DIR/requirements-runtime.txt"
else
    source "$VENV_DIR/bin/activate"
    log "Using existing venv: $VENV_DIR"
fi

# Verify tools work
"${PY[@]}" "$TOOLS_DIR/vcf_transform/vcf_to_beacon.py" --help >/dev/null 2>&1 \
    || die "vcf_to_beacon.py --help failed. Check dependencies."

log "Python $("${PY[@]}" --version 2>&1) ready"

# --- Create tuned config for ILIFU ---
step 2 "Creating optimized config for ILIFU"

ILIFU_CONFIG="$OUTPUT_DIR/ilifu_settings.yaml"
mkdir -p "$OUTPUT_DIR"

cat > "$ILIFU_CONFIG" <<YAML
# Auto-generated config for ILIFU pipeline run
# $(date '+%Y-%m-%d %H:%M:%S')

mongodb:
  host: "localhost"
  port: $TUNNEL_PORT
  database: "$MONGO_DB"
  connection_timeout: 30
  collections:
    variants: "variants"
    individuals: "individuals"
    datasets: "datasets"
    biosamples: "biosamples"
    analyses: "analyses"
    cohorts: "cohorts"
    filtering_terms: "filtering_terms"

vcf:
  supported_assemblies: ["GRCh37", "GRCh38", "hg19", "hg38"]
  default_assembly: "$ASSEMBLY"
  required_fields: ["CHROM", "POS", "REF", "ALT", "QUAL", "FILTER"]
  info_fields: ["AF", "AC", "AN", "DP", "GENE", "CSQ", "ANN"]
  format_fields: ["GT", "DP", "GQ", "AD"]
  quality_filters:
    min_qual: 20
    min_depth: 10
    max_missing_rate: 0.1

phenotypes:
  supported_ontologies: ["HPO", "MONDO", "ORDO", "NCIT", "SNOMED"]
  default_ontology: "HPO"
  supported_formats: ["csv", "tsv", "xlsx", "json"]

validation:
  strict_mode: false
  required_fields_check: true
  type_validation: true
  range_validation: true
  genome_validation: true

processing:
  batch_size: $BATCH_SIZE
  max_workers: $MAX_WORKERS
  memory_limit: 8192
  temp_dir: "/tmp/beacon_transform"
  log_level: "INFO"
  show_progress: true

output:
  default_format: "json"
  supported_formats: ["json", "bson", "csv", "tsv"]
  pretty_json: true
  include_metadata: true
YAML

log "Config written: $ILIFU_CONFIG"

# --- Transform VCF ---
step 3 "Transforming VCF to Beacon v2 JSON"

VCF_OUTPUT="$OUTPUT_DIR/vcf_output"
log "Input:  $VCF_FILE"
log "Output: $VCF_OUTPUT"

"${PY[@]}" "$TOOLS_DIR/vcf_transform/vcf_to_beacon.py" "$VCF_FILE" \
    --output "$VCF_OUTPUT" \
    --assembly "$ASSEMBLY" \
    --dataset-id "$DATASET_ID" \
    --config "$ILIFU_CONFIG" \
    --verbose

# Check output was created
[[ -f "$VCF_OUTPUT/variants_batch.jsonl" ]] || die "variants_batch.jsonl not created"
VARIANT_COUNT=$(wc -l < "$VCF_OUTPUT/variants_batch.jsonl")
log "Variants produced: $VARIANT_COUNT"

if [[ -f "$VCF_OUTPUT/individuals.json" ]]; then
    IND_COUNT=$("${PY[@]}" -c "import json; print(len(json.load(open('$VCF_OUTPUT/individuals.json'))))")
    log "Individuals found: $IND_COUNT"
fi

# --- Transform phenotypes (optional) ---
if [[ -n "$PHENOTYPE_FILE" ]]; then
    step 4 "Transforming phenotype data"

    PHENO_OUTPUT="$OUTPUT_DIR/phenotype_output"
    INDIVIDUALS_ARG=""
    if [[ -f "$VCF_OUTPUT/individuals.json" ]]; then
        INDIVIDUALS_ARG="--individuals $VCF_OUTPUT/individuals.json"
    fi

    "${PY[@]}" "$TOOLS_DIR/phenotype_transform/phenotype_to_beacon.py" "$PHENOTYPE_FILE" \
        --output "$PHENO_OUTPUT" \
        --config "$ILIFU_CONFIG" \
        $INDIVIDUALS_ARG \
        --verbose

    log "Phenotype output: $PHENO_OUTPUT"
fi

# --- Validate ---
if [[ "$SKIP_VALIDATE" != true ]]; then
    step 5 "Validating transformed data"

    log "Validating variants..."
    "${PY[@]}" "$TOOLS_DIR/validation/validate_json.py" "$VCF_OUTPUT/variants_batch.jsonl" \
        --schema-type variant --strict

    log "Validating individuals..."
    "${PY[@]}" "$TOOLS_DIR/validation/validate_json.py" "$VCF_OUTPUT/individuals.json" \
        --schema-type individual --strict

    if [[ -n "$PHENOTYPE_FILE" ]] && [[ -d "$PHENO_OUTPUT" ]]; then
        log "Validating phenotypes..."
        "${PY[@]}" "$TOOLS_DIR/validation/validate_json.py" "$PHENO_OUTPUT/phenotypes.json" \
            --schema-type phenotype --strict || log "WARNING: Phenotype validation had issues"
    fi

    log "Validation complete"
else
    log "Skipping validation (--skip-validate)"
fi

# --- Import to MongoDB ---
if [[ "$SKIP_IMPORT" != true ]]; then
    step 6 "Importing to production MongoDB"

    # Check if SSH tunnel is active
    if ! nc -z localhost "$TUNNEL_PORT" 2>/dev/null; then
        log "Starting SSH tunnel to beacon server..."
        ssh -f -N -L "${TUNNEL_PORT}:localhost:27017" "$BEACON_HOST" \
            || die "Failed to create SSH tunnel. Ensure SSH access to $BEACON_HOST"
        sleep 2

        if ! nc -z localhost "$TUNNEL_PORT" 2>/dev/null; then
            die "SSH tunnel not reachable on port $TUNNEL_PORT"
        fi
        log "SSH tunnel established on port $TUNNEL_PORT"
        TUNNEL_STARTED=true
    else
        log "SSH tunnel already active on port $TUNNEL_PORT"
        TUNNEL_STARTED=false
    fi

    MONGO_URI="mongodb://localhost:${TUNNEL_PORT}/"

    log "Importing variants..."
    "${PY[@]}" "$TOOLS_DIR/data_import/import_to_mongo.py" "$VCF_OUTPUT/variants_batch.jsonl" \
        --db "$MONGO_DB" --collection variants \
        --mongo-uri "$MONGO_URI" --verbose

    log "Importing individuals..."
    "${PY[@]}" "$TOOLS_DIR/data_import/import_to_mongo.py" "$VCF_OUTPUT/individuals.json" \
        --db "$MONGO_DB" --collection individuals \
        --mongo-uri "$MONGO_URI" --verbose

    if [[ -n "$PHENOTYPE_FILE" ]] && [[ -f "$PHENO_OUTPUT/phenotypes.json" ]]; then
        log "Importing phenotypes..."
        "${PY[@]}" "$TOOLS_DIR/data_import/import_to_mongo.py" "$PHENO_OUTPUT/phenotypes.json" \
            --db "$MONGO_DB" --collection phenotypes \
            --mongo-uri "$MONGO_URI" --verbose
    fi

    # Flush Redis cache on beacon server
    log "Flushing Redis cache..."
    ssh "$BEACON_HOST" "docker exec beacon-redis redis-cli FLUSHDB" 2>/dev/null || true

    # Cleanup tunnel if we started it
    if [[ "$TUNNEL_STARTED" == true ]]; then
        log "Cleaning up SSH tunnel..."
        pkill -f "ssh.*-L.*${TUNNEL_PORT}:localhost:27017.*${BEACON_HOST}" 2>/dev/null || true
    fi

    log "Import complete"
else
    log "Skipping import (--skip-import)"
fi

# --- Summary ---
step 7 "Pipeline Summary"

echo
echo "Output directory: $OUTPUT_DIR"
echo
echo "Files created:"
find "$OUTPUT_DIR" -type f -name "*.json*" -printf "  %p (%s bytes)\n" 2>/dev/null \
    || find "$OUTPUT_DIR" -type f -name "*.json*" -exec ls -lh {} \; 2>/dev/null

echo
if [[ "$SKIP_IMPORT" != true ]]; then
    echo "Verify in Beacon API:"
    echo "  curl 'http://<your-server-ip>:8000/api/datasets'"
    echo "  curl 'http://<your-server-ip>:8000/api/g_variants?assemblyId=${ASSEMBLY}&referenceName=1&start=100000'"
fi

log "Done!"
