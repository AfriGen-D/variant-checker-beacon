#!/usr/bin/env bash
#SBATCH --job-name=beacon-load
#SBATCH --output=beacon-load-%j.log
#SBATCH --error=beacon-load-%j.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=7-00:00:00

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# AfriGend Beacon v2 — ILIFU SLURM Head Job
# Creates SSH tunnel to beacon MongoDB, then runs Nextflow pipeline
#
# Usage:
#   sbatch ILIFU/beacon.sh --vcf /path/to/data.vcf.gz --dataset H3AR3b
#   sbatch ILIFU/beacon.sh --vcf /path/to/data.vcf.gz --phenotypes /path/to/pheno.csv
# ──────────────────────────────────────────────────────────────────────────────

# --- Configuration ---
BEACON_HOST="${BEACON_HOST:-H3ABN-Beacon_beacon2.h3abionet.org-ilifu}"
TUNNEL_PORT="${TUNNEL_PORT:-27018}"
PIPELINE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Parse arguments (pass-through to Nextflow) ---
NF_ARGS=()
VCF_FILE=""
DATASET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --vcf)      VCF_FILE="$2"; shift 2 ;;
        --dataset)  DATASET="$2"; shift 2 ;;
        *)          NF_ARGS+=("$1"); shift ;;
    esac
done

[[ -n "$VCF_FILE" ]] || { echo "Error: --vcf is required"; exit 1; }
[[ -n "$DATASET" ]]  || { echo "Error: --dataset is required"; exit 1; }

echo "━━━ Beacon v2 Data Loading — ILIFU ━━━"
echo "VCF:     $VCF_FILE"
echo "Dataset: $DATASET"
echo "Node:    $(hostname)"
echo "Date:    $(date)"
echo

# --- Create SSH tunnel to beacon MongoDB ---
echo "Creating SSH tunnel to ${BEACON_HOST} (port ${TUNNEL_PORT})..."

ssh -f -N -o StrictHostKeyChecking=no -o ServerAliveInterval=60 \
    -L "${TUNNEL_PORT}:localhost:27017" "$BEACON_HOST"

sleep 2

if ! nc -z localhost "$TUNNEL_PORT" 2>/dev/null; then
    echo "ERROR: SSH tunnel not reachable on port $TUNNEL_PORT"
    exit 1
fi
echo "SSH tunnel established on port $TUNNEL_PORT"

# --- Cleanup on exit ---
cleanup() {
    echo "Cleaning up SSH tunnel..."
    pkill -f "ssh.*-L.*${TUNNEL_PORT}:localhost:27017.*${BEACON_HOST}" 2>/dev/null || true
    echo "Done"
}
trap cleanup EXIT

# --- Load Nextflow ---
module load nextflow 2>/dev/null || true
export NXF_HOME="${HOME}/.nextflow"
export NXF_WORK="/scratch3/users/mamana/nextflow_work/beacon"

# --- Run pipeline ---
echo
echo "Launching Nextflow pipeline..."

cd "$PIPELINE_DIR"

nextflow run main.nf \
    -profile singularity,slurm \
    -c ILIFU/beacon.config \
    -resume \
    --dataset_name "$DATASET" \
    --vcf_file "$VCF_FILE" \
    "${NF_ARGS[@]}"

echo
echo "Pipeline complete. Check results at: /cbio/users/mamana/beacon_output/${DATASET}/"
