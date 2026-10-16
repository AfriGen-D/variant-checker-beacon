#!/usr/bin/env bash
# Submit many VCF files to Slurm as jobs and load them as ONE dataset.
#
#   1. a job ARRAY transforms and validates the files, one task per file, at most
#      --max-parallel at a time (no database is touched);
#   2. with --import, a second job waits for every task to succeed, then imports the
#      files one after another and registers the dataset once.
#
# Why two stages: the transforms are independent and can run side by side; the
# import goes through one SSH tunnel, and a full pipeline run closes the tunnel it
# opened, so imports must run one at a time (and the dataset record must be written
# after the last one, because it counts the variants it finds).
#
# Usage:
#   scripts/submit_multi_vcf.sh --dataset-file dataset.yaml \
#       --container /cbio/users/$USER/beacon-tools.sif  /path/to/vcfs/*.vcf.gz
#
#   or keep the file names in a text file (one path per line) and pass that:
#   scripts/submit_multi_vcf.sh --dataset-file dataset.yaml \
#       --container /cbio/users/$USER/beacon-tools.sif  --vcf-list vcf_files.txt
#
# Run it from a shell where `sbatch` works (a login or compute node on the cluster).
# -e: stop on the first failing command; -u: an unset variable is an error;
# pipefail: a pipeline fails if any stage fails.
set -euo pipefail

# The jobs run scripts/run_ilifu_pipeline.sh from the repository this script lives
# in, so find that repository from the script's own location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Defaults. Every one can be changed with the option of the same name ---
# What to load, and how to run the tools.
DATASET_FILE=""; DATASET_ID=""; CONTAINER=""; RUNTIME=""; ASSEMBLY=""
# Work folder: one sub-folder per VCF, plus logs/ and the generated job scripts.
OUT="/cbio/users/${USER:-$(id -un)}/beacon_multi"
# Slurm resources for ONE transform task (the import job has its own fixed size).
MAX_PARALLEL=4; CPUS=4; MEM="32G"; TIME="1-00:00:00"
# DO_IMPORT: transform, then import. IMPORT_ONLY: import output that already exists.
# DRY_RUN: write the job scripts but submit nothing.
SBATCH_ARGS=""; DO_IMPORT=false; IMPORT_ONLY=false; DRY_RUN=false
VCFS=()          # VCF paths given on the command line
LISTS=()         # text files (--vcf-list) that name more VCF paths

# Report a usage problem and stop. Exit code 2 means "bad arguments", not "job failed".
die() { echo "Error: $*" >&2; exit 2; }

usage() {
    cat <<'USAGE'
Usage: submit_multi_vcf.sh [options] [VCF ...]

  --vcf-list <file>       A text file with one VCF path per line (blank lines and lines
                          starting with # are ignored). Repeatable; can be combined with
                          VCF paths on the command line. Relative paths are relative to
                          the folder you run this from.
  --dataset-file <file>   dataset.yaml (id, name, ...). Preferred.
  --dataset-id <id>       The dataset id, when you have no dataset file.
  --container <image>     The tools image (.sif, docker:// URI, or a Docker image).
  --runtime <name>        Passed to the pipeline (singularity, apptainer, docker).
  --assembly <id>         Genome assembly (default: the pipeline's, GRCh38).
  --output <dir>          Work folder (default: /cbio/users/$USER/beacon_multi).
  --max-parallel <n>      Transform at most n files at once (default 4).
  --cpus <n>              CPUs per transform task (default 4).
  --mem <size>            Memory per transform task (default 32G).
  --time <d-hh:mm:ss>     Time limit per transform task (default 1-00:00:00).
  --sbatch-args "<args>"  Extra options for every sbatch, e.g. "--nodelist=compute-[205,209]".
  --import                Also submit the import job, after every transform succeeded.
  --import-only           Submit only the import job, for output already transformed.
  --dry-run               Write the job scripts and show what would be submitted.

Nothing is written to a database unless you pass --import or --import-only.
USAGE
}

# --- Read the command line. Anything that is not an option is a VCF file ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --vcf-list)     LISTS+=("${2:?--vcf-list needs a file name}"); shift 2 ;;
        --dataset-file) DATASET_FILE="${2:?--dataset-file needs a value}"; shift 2 ;;
        --dataset-id)   DATASET_ID="${2:?--dataset-id needs a value}"; shift 2 ;;
        --container)    CONTAINER="${2:?--container needs a value}"; shift 2 ;;
        --runtime)      RUNTIME="${2:?--runtime needs a value}"; shift 2 ;;
        --assembly)     ASSEMBLY="${2:?--assembly needs a value}"; shift 2 ;;
        --output)       OUT="${2:?--output needs a value}"; shift 2 ;;
        --max-parallel) MAX_PARALLEL="${2:?--max-parallel needs a value}"; shift 2 ;;
        --cpus)         CPUS="${2:?--cpus needs a value}"; shift 2 ;;
        --mem)          MEM="${2:?--mem needs a value}"; shift 2 ;;
        --time)         TIME="${2:?--time needs a value}"; shift 2 ;;
        --sbatch-args)  SBATCH_ARGS="${2:?--sbatch-args needs a value}"; shift 2 ;;
        --import)       DO_IMPORT=true; shift ;;
        --import-only)  IMPORT_ONLY=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage; exit 0 ;;
        # An unknown option is an error, not a file name (catches typos such as --max-paralel).
        -*)             die "unknown option: $1 (see --help)" ;;
        *)              VCFS+=("$1"); shift ;;
    esac
done

# --- Validate everything before writing or submitting anything ---
[[ -n "$DATASET_FILE" || -n "$DATASET_ID" ]] || die "a dataset is required: --dataset-file dataset.yaml (preferred) or --dataset-id <id>"
[[ -n "$CONTAINER" ]] || die "--container is required: the tools image the jobs run (a .sif file, or an image name)"
# These two go straight into the #SBATCH header, so they must be plain numbers.
[[ "$MAX_PARALLEL" =~ ^[1-9][0-9]*$ ]] || die "--max-parallel must be a positive whole number, got '$MAX_PARALLEL'"
[[ "$CPUS" =~ ^[1-9][0-9]*$ ]] || die "--cpus must be a positive whole number, got '$CPUS'"
# --import transforms first, --import-only does not: asking for both is ambiguous.
if [[ "$IMPORT_ONLY" == true && "$DO_IMPORT" == true ]]; then die "--import and --import-only contradict each other"; fi

# Absolute path of a file. The jobs start in the repository folder, so a relative
# path given here would point somewhere else when the job runs.
abspath() { ( cd "$(dirname "$1")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "$1")" ) || printf '%s\n' "$1"; }
# The folder name for a VCF: its file name without .gz / .vcf / .bcf
# (chr1.vcf.gz -> chr1). The job scripts compute the same name the same way.
name_of() { local n; n="$(basename "$1")"; n="${n%.gz}"; n="${n%.vcf}"; n="${n%.bcf}"; printf '%s' "$n"; }

if [[ -n "$DATASET_FILE" ]]; then
    [[ -f "$DATASET_FILE" ]] || die "dataset file not found: $DATASET_FILE"
    DATASET_FILE="$(abspath "$DATASET_FILE")"
    [[ "$DATASET_FILE" != *[[:space:]]* ]] || die "the dataset file path must not contain a space: $DATASET_FILE"
fi
# The paths are written unquoted into the job scripts and the pipeline command
# line, so a space would split them into two words.
[[ "$OUT" != *[[:space:]]* ]] || die "the --output path must not contain a space: $OUT"

# Gather every VCF to load into ENTRIES, remembering where each one was named
# (WHERE) so an error can point at the right line. Files from --vcf-list come first,
# in the order given, then the paths from the command line.
ENTRIES=(); WHERE=()
for lf in ${LISTS[@]+"${LISTS[@]}"}; do
    [[ -f "$lf" ]] || die "VCF list not found: $lf"
    lineno=0
    # `|| [[ -n $line ]]` also reads a last line that has no trailing newline.
    while IFS= read -r line || [[ -n "$line" ]]; do
        lineno=$((lineno + 1))
        line="${line#"${line%%[![:space:]]*}"}"               # trim leading blanks
        line="${line%"${line##*[![:space:]]}"}"               # trim trailing blanks (and a Windows \r)
        if [[ -z "$line" || "$line" == \#* ]]; then continue; fi   # blank or comment
        ENTRIES+=("$line"); WHERE+=("line $lineno of $lf")
    done < "$lf"
done
for v in ${VCFS[@]+"${VCFS[@]}"}; do ENTRIES+=("$v"); WHERE+=("the command line"); done
[[ ${#ENTRIES[@]} -gt 0 ]] || die "give at least one VCF file, on the command line or with --vcf-list (see --help)"

# Check every VCF and collect its absolute path (ABS) and folder name (NAMES).
ABS=(); NAMES=()
for i in "${!ENTRIES[@]}"; do
    v="${ENTRIES[$i]}"
    [[ -f "$v" ]] || die "VCF not found: $v (named on ${WHERE[$i]})"
    a="$(abspath "$v")"
    [[ "$a" != *[[:space:]]* ]] || die "a VCF path must not contain a space: $a"
    n="$(name_of "$a")"
    # Two inputs with the same base name would write to the same folder and overwrite
    # each other, e.g. a/chr1.vcf.gz and b/chr1.vcf.gz. (${arr[@]+...} keeps the
    # empty first round working on bash 3.2 with `set -u`.)
    for seen in ${NAMES[@]+"${NAMES[@]}"}; do
        [[ "$seen" != "$n" ]] || die "two files would write to the same folder ('$n'): $a — rename one"
    done
    ABS+=("$a"); NAMES+=("$n")
done
N=${#ABS[@]}
# Never ask for more parallel slots than there are files (the array is 1..N).
PAR=$MAX_PARALLEL; (( PAR > N )) && PAR=$N

# --- Arguments every pipeline call shares ---
# The transform tasks and the import job must describe the dataset and the tools the
# same way, so the options are built once, here, and pasted into both job scripts.
COMMON=""
if [[ -n "$DATASET_FILE" ]]; then COMMON+=" --dataset-file $DATASET_FILE"; fi
if [[ -n "$DATASET_ID" ]]; then COMMON+=" --dataset-id $DATASET_ID"; fi
COMMON+=" --container $CONTAINER"
if [[ -n "$RUNTIME" ]]; then COMMON+=" --runtime $RUNTIME"; fi
if [[ -n "$ASSEMBLY" ]]; then COMMON+=" --assembly $ASSEMBLY"; fi

# --- Write the job scripts ---
# The unquoted JOB heredocs below expand the ${...} values now, when this script
# runs. Anything that Slurm must expand when the job runs (the array task number,
# the VCF name) is written with a backslash: \$VAR.
mkdir -p "$OUT/logs"
# One path per line. Task K of the array handles line K, so the order here is the
# task numbering.
printf '%s\n' "${ABS[@]}" > "$OUT/vcf_list.txt"

cat > "$OUT/transform.sbatch" <<JOB
#!/bin/bash
#SBATCH --job-name=beacon-transform
#SBATCH --array=1-${N}%${PAR}
#SBATCH --cpus-per-task=${CPUS}
#SBATCH --mem=${MEM}
#SBATCH --time=${TIME}
#SBATCH --output=${OUT}/logs/transform_%a.log
# One task per VCF: line \$SLURM_ARRAY_TASK_ID of vcf_list.txt. No database is touched.
set -euo pipefail
cd "${REPO_DIR}"
VCF=\$(sed -n "\${SLURM_ARRAY_TASK_ID}p" "${OUT}/vcf_list.txt")
NAME=\$(basename "\$VCF"); NAME=\${NAME%.gz}; NAME=\${NAME%.vcf}; NAME=\${NAME%.bcf}
./scripts/run_ilifu_pipeline.sh "\$VCF"${COMMON} --skip-import --output "${OUT}/\$NAME"
JOB

# The import job is only written when something will import: a transform-only run
# must leave nothing behind that could be submitted by mistake.
if [[ "$DO_IMPORT" == true || "$IMPORT_ONLY" == true ]]; then
cat > "$OUT/import.sbatch" <<JOB
#!/bin/bash
#SBATCH --job-name=beacon-import
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=0-12:00:00
#SBATCH --output=${OUT}/logs/import.log
# Import each transformed file in turn (one SSH tunnel, one at a time). Each call also
# (re)registers the dataset, so the last call leaves the record with the final counts.
set -euo pipefail
cd "${REPO_DIR}"
while IFS= read -r VCF; do
    NAME=\$(basename "\$VCF"); NAME=\${NAME%.gz}; NAME=\${NAME%.vcf}; NAME=\${NAME%.bcf}
    echo "=== importing \$NAME"
    ./scripts/run_ilifu_pipeline.sh "\$VCF"${COMMON} --import-only --output "${OUT}/\$NAME"
done < "${OUT}/vcf_list.txt"
JOB
fi

# --- Submit ---
# --sbatch-args "a b" becomes the words a and b, added to every sbatch call below.
EXTRA=(); if [[ -n "$SBATCH_ARGS" ]]; then read -r -a EXTRA <<< "$SBATCH_ARGS"; fi

if [[ "$DRY_RUN" == true ]]; then
    echo "Dry run: wrote $OUT/transform.sbatch and $OUT/import.sbatch; nothing submitted."
    exit 0
fi

# Stage 1: the transform array. Skipped with --import-only (output already exists).
# --parsable prints just the job id (and ";cluster" on multi-cluster setups, which
# the next line strips).
ARRAY_ID=""
if [[ "$IMPORT_ONLY" != true ]]; then
    ARRAY_ID="$(sbatch --parsable ${EXTRA[@]+"${EXTRA[@]}"} "$OUT/transform.sbatch")"
    ARRAY_ID="${ARRAY_ID%%;*}"
    echo "Submitted transform array $ARRAY_ID: $N file(s), at most $PAR at a time."
fi

# Stage 2: the import job.
#   --import       wait for the whole array: afterok means "only if EVERY task
#                  succeeded"; --kill-on-invalid-dep=yes cancels this job when that
#                  can no longer happen, instead of leaving it pending forever.
#   --import-only  nothing to wait for, the output was produced by an earlier run.
IMPORT_ID=""
if [[ "$DO_IMPORT" == true ]]; then
    IMPORT_ID="$(sbatch --parsable --dependency=afterok:"$ARRAY_ID" --kill-on-invalid-dep=yes \
        ${EXTRA[@]+"${EXTRA[@]}"} "$OUT/import.sbatch")"
    echo "Submitted import job $IMPORT_ID: starts only after every transform task succeeds."
elif [[ "$IMPORT_ONLY" == true ]]; then
    IMPORT_ID="$(sbatch --parsable ${EXTRA[@]+"${EXTRA[@]}"} "$OUT/import.sbatch")"
    echo "Submitted import job $IMPORT_ID (importing output that already exists)."
else
    echo
    echo "Nothing is written to a database. To import these results afterwards, run the"
    echo "same command with --import-only (or add --import next time)."
fi

echo
echo "Watch:   squeue --me"
[[ -z "$ARRAY_ID" ]] || echo "         sacct -j $ARRAY_ID --format=JobID,State,Elapsed,MaxRSS"
echo "Logs:    $OUT/logs/   (transform_<n>.log per file, import.log)"
