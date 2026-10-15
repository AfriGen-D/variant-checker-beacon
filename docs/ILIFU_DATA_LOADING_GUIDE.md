# Loading VCF Data into Beacon v2 on ILIFU

This guide walks through transforming your VCF files (any cohort or dataset) into GA4GH Beacon v2 format and loading it into the production MongoDB instance.

## Architecture Overview

```
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────────────┐
│  ILIFU Compute Node │     │  SSH Tunnel       │     │  Beacon Server        │
│                     │     │                   │     │  (<your-server-ip>)      │
│  VCF files          │────>│  localhost:27017  │────>│  MongoDB (Docker)     │
│  ↓                  │     │  ←→               │     │  ↓                    │
│  vcf_to_beacon.py   │     └──────────────────┘     │  Beacon API           │
│  ↓                  │                               │  ↓                    │
│  validate_json.py   │                               │  Frontend             │
│  ↓                  │                               └───────────────────────┘
│  import_to_mongo.py │
└─────────────────────┘
```

**Why ILIFU?** VCF transformation is compute-intensive (parsing millions of variants). ILIFU compute nodes provide the CPU, memory, and direct access to the data on `/cbio` that this requires.

## Prerequisites

| Requirement | Details |
|---|---|
| ILIFU SSH access | `ssh <your-ilifu-username>@slurm.ilifu.ac.za` (or the `ilifu` alias below) |
| Beacon server SSH | `ssh <your-ssh-alias>` |
| Container runtime | Singularity/Apptainer on ILIFU (Option A in Step 2), or Python 3.9+ (Option B) |
| VCF data | `.vcf.gz` files in `/cbio/dbs/` or `/cbio/projects/` |

Your ILIFU username is the one you were given when your account was created; it
is not necessarily the username on your own computer. To avoid typing it every
time, add an alias to `~/.ssh/config` on your own computer, once:

```text
Host ilifu
    HostName slurm.ilifu.ac.za
    User <your-ilifu-username>
```

Then `ssh ilifu` is the same as `ssh <your-ilifu-username>@slurm.ilifu.ac.za`.

## Quick Start (Automated Pipeline)

The fastest path — a single script handles everything. Paths in this guide use
`$USER`, your ILIFU username, so the commands work for any user as written.
The repository is assumed to be cloned as `variant-checker-beacon` in your
`/cbio/users/$USER` directory (Step 2 below does this).

```bash
# 1. SSH into ILIFU (from your own computer)
ssh <your-ilifu-username>@slurm.ilifu.ac.za   # or: ssh ilifu

# 2. Get a compute node (NEVER run on login node)
srun --pty --nodes=1 --ntasks-per-node=1 --cpus-per-task=4 \
     --mem=32G --time=7-0:0:0 --nodelist=compute-[205,209] bash

# 3. Get the repository and the tools image (once)
cd /cbio/users/$USER
git clone https://github.com/AfriGen-D/variant-checker-beacon.git
singularity pull beacon-tools.sif docker://ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest

# 4. Run the pipeline: the tools run from the container, so nothing is installed
cd variant-checker-beacon
./scripts/run_ilifu_pipeline.sh /path/to/your_data.vcf.gz \
    --container /cbio/users/$USER/beacon-tools.sif
```

`--container` takes a `.sif` file or a `docker://` URI (run with Singularity or
Apptainer), or a plain Docker image name such as
`ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest` (run with Docker,
on a server or workstation). `--runtime` overrides the choice. Without
`--container` the script uses a Python environment instead and creates it on the
first run (Step 2, Option B).

### Pipeline Options

```bash
# With phenotype data
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --phenotypes /path/to/phenotypes.csv

# Transform + validate only (no MongoDB import)
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz --skip-import

# Custom assembly and output location
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --assembly GRCh37 \
    --output /scratch3/users/$USER/beacon_output

# Preview what will happen (no execution)
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz --dry-run

# Tune for large datasets
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --batch-size 10000 \
    --workers 4
```

## Step-by-Step Guide (Manual)

If you prefer to run each step individually for more control.

### Step 1: Get a Compute Node

```bash
ssh <your-ilifu-username>@slurm.ilifu.ac.za   # or: ssh ilifu

# Request interactive session with resources for VCF processing
srun --pty --nodes=1 --ntasks-per-node=1 --cpus-per-task=4 \
     --mem=32G --time=7-0:0:0 --nodelist=compute-[205,209] bash
```

**Resource guidance:**

| Dataset Size | CPUs | Memory | Notes |
|---|---|---|---|
| < 1M variants | 2 | 16G | Small panel / exome |
| 1-10M variants | 4 | 32G | Standard WGS |
| 10M+ variants | 8 | 64G | Large cohort VCF |

### Step 2: Install the Tools

First get the repository, which holds the scripts and the tools' configuration:

```bash
cd /cbio/users/$USER

# Clone if not already present
git clone https://github.com/AfriGen-D/variant-checker-beacon.git
```

Then choose a route. Each one ends by defining a small shell function `beacon`,
which runs a program in the right place, and the variable `$TOOLS`, which says
where the tools live. Every later step is written with them, so the commands are
the same whichever route you choose (a function rather than a variable, so it
behaves the same in bash and zsh). Define them again in each new shell session,
or put the lines in your `~/.bashrc`.

#### Option A (recommended): a container

Nothing to install or reinstall: the image carries Python, every library,
`cyvcf2` and `bcftools`. Use Singularity on ILIFU (A1) or Docker on a server or
workstation where you have it (A2).

#### A1. Singularity/Apptainer (ILIFU)

On a node where the command is `apptainer`, use that instead; the options are
the same. `/cbio` and `/scratch3` are bound so your data is visible inside.

```bash
cd /cbio/users/$USER

# Once: pull the image into a single .sif file in your own space.
singularity pull beacon-tools.sif docker://ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest

# In every shell session:
beacon() { singularity exec --bind /cbio,/scratch3 "/cbio/users/$USER/beacon-tools.sif" "$@"; }
TOOLS=/opt/beacon-tools

# Verify installation
beacon bcftools --version | head -1
beacon python $TOOLS/vcf_transform/vcf_to_beacon.py --help
```

#### A2. Docker

`DATA` is the directory that holds your VCFs and receives the output; it is
mounted at the same path inside the container. Replace `/cbio/users/$USER` in
the later steps with it. `--network host` lets the container reach the SSH
tunnel to MongoDB in Step 7 on Linux.

```bash
# Once: pull the image.
docker pull ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest

# In every shell session:
DATA=$HOME/beacon_data
beacon() { docker run --rm --network host -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$DATA:$DATA" -w "$DATA" --entrypoint= ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest "$@"; }
TOOLS=/opt/beacon-tools

# Verify installation
beacon bcftools --version | head -1
beacon python $TOOLS/vcf_transform/vcf_to_beacon.py --help
```

The image is rebuilt and published from this repository's `main` branch. Pull it
again (`singularity pull --force ...` or `docker pull ...`) to update.

#### A3. Build the image yourself

Use this to change the tools, to work without access to `ghcr.io`, or to test a
branch. You need Docker and a checkout of this repository. Build from the
repository root, on a machine with the same CPU type as the machine that will
run it (ILIFU is x86-64, as are most servers and Intel Macs):

```bash
cd variant-checker-beacon
docker build -f nextflow/docker/Dockerfile.tools -t beacon-tools:local .
```

On an Apple Silicon Mac that plain build makes an ARM image, which will not run
on ILIFU. Build for x86-64 instead (or build on an x86-64 Linux machine):

```bash
docker buildx build --platform linux/amd64 --load -f nextflow/docker/Dockerfile.tools -t beacon-tools:local .
```

With Docker, use `beacon-tools:local` in place of the `ghcr.io/...` name in A2, or
pass `--container beacon-tools:local` to `run_ilifu_pipeline.sh`. ILIFU has no
Docker, so save the image to a file, copy it across and convert it there:

```bash
# On your own machine: save the image and copy it to ILIFU.
docker save -o beacon-tools.tar beacon-tools:local
scp beacon-tools.tar <your-ilifu-username>@transfer.ilifu.ac.za:/cbio/users/<your-ilifu-username>/

# On an ILIFU compute node: convert it to the single .sif file A1 uses.
cd /cbio/users/$USER
singularity build beacon-tools.sif docker-archive://beacon-tools.tar
```

Keep the archive a plain `.tar`: Singularity rejects a gzipped one with
`invalid tar header`. From here the `beacon()` function in A1 works unchanged.

#### Option B: a Python environment

Use this if you cannot run containers.

```bash
cd /cbio/users/$USER/variant-checker-beacon/afrigend-beacon2-tools

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the runtime dependencies from prebuilt wheels (no compiler needed).
# Use requirements-runtime.txt, not requirements.txt: the latter pins numpy and
# cyvcf2 versions that have no Python 3.12 build and fails on current nodes.
pip install --upgrade pip "setuptools<70" wheel
pip install --only-binary=:all: -r requirements-runtime.txt

# The function and variable every later step uses
beacon() { "$@"; }
TOOLS=$PWD

# Verify installation
python $TOOLS/vcf_transform/vcf_to_beacon.py --help
python $TOOLS/validation/validate_json.py --help
python $TOOLS/data_import/import_to_mongo.py --help
```

**Troubleshooting a Python environment (Option B):**
- `cyvcf2` is installed as a prebuilt wheel that bundles htslib, so you do not
  need htslib, a compiler or root. If no wheel exists for your Python, pip
  stops with `No matching distribution` instead of trying to compile.
- If `pip install` is slow, try:
  `pip install --only-binary=:all: --no-cache-dir -r requirements-runtime.txt`
- `requirements.txt` is the full set pinned for Python 3.9 development and CI.
  Do not use it on the cluster; see the Common Issues entry below.

**If `python3 -m venv .venv` fails** with `ensurepip is not available` and suggests `apt install python3.12-venv`: you cannot install system packages on the cluster, so create the venv without them. The simplest way is `uv`, which installs into your home directory and needs no root:

```bash
rm -rf .venv                      # remove the half-created directory
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv --seed .venv
source .venv/bin/activate
```

Then continue with the `pip install` lines above. To avoid installing a new tool, build the venv without pip and bootstrap pip into it:

```bash
rm -rf .venv
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
source .venv/bin/activate
```

Both methods need outbound internet from the node. If the node has none, create the venv from a Python module or a conda environment whose build includes `venv` (`module avail python`, `which conda mamba`).

### Step 3: Locate Your VCF Files

```bash
# Your workspace on ILIFU:
ls /cbio/users/$USER/

# Search for VCF files
find /cbio/dbs/ -name "*.vcf.gz" -type f 2>/dev/null | head -20
find /cbio/projects/ -name "*.vcf.gz" -type f 2>/dev/null | head -20

# Check a VCF file header to confirm assembly and samples.
# bcftools is inside the container; with a Python environment (Option B) run
# `module load bcftools` first.
beacon bcftools view -h /path/to/file.vcf.gz | head -30
beacon bcftools query -l /path/to/file.vcf.gz | wc -l   # count samples
```

**Use bcftools to inspect and prepare the VCF before transforming it.** It is
far faster than Python on large files, and a small test slice lets you check the
whole pipeline in minutes before committing to a full run:

```bash
# Contigs the file uses, with their variant counts (needs a .tbi/.csi index)
beacon bcftools index -s /path/to/file.vcf.gz

# Create the index if the file has none
beacon bcftools index -t /path/to/file.vcf.gz

# A small test slice: one region, PASS variants only, compressed and indexed.
# Use the contig name exactly as `index -s` printed it above (22 or chr22).
beacon bcftools view -f PASS -r 22:16000000-17000000 /path/to/file.vcf.gz \
    -Oz -o /cbio/users/$USER/test_slice.vcf.gz
beacon bcftools index -t /cbio/users/$USER/test_slice.vcf.gz
```

### Step 4: Transform VCF to Beacon JSON

```bash
beacon python $TOOLS/vcf_transform/vcf_to_beacon.py /path/to/your_data.vcf.gz \
    --output /cbio/users/$USER/beacon_output/vcf_output \
    --assembly GRCh38 \
    --config $TOOLS/config/settings.yaml \
    --verbose
```

Add `--dataset-id <id>` to attribute the variants to a dataset. Without it the
records carry an empty `dataset_ids`; `run_ilifu_pipeline.sh` instead defaults to
`H3A_V6_AFR`, the production dataset, so pass `--dataset-id` there too whenever
the data belongs to another dataset.

**What this produces:**

| File | Description |
|---|---|
| `variants_batch.jsonl` | One JSON variant record per line (JSONL format) |
| `individuals.json` | Individual records derived from VCF sample names |
| `variant_genotypes.json` | Reserved: always an empty list `[]` today; genotypes stay in the VCF |
| `transformation_summary.json` | Stats: variants processed/filtered, individuals found |

**Understanding the output:**

```text
// variants_batch.jsonl (one line per variant)
{"id": "1:100001:A:T", "assembly_id": "GRCh38", "reference_name": "1",
 "start": 100000, "end": 100001, "reference_bases": "A",
 "alternate_bases": "T", "variant_type": "SNV", "annotations": [...]}

// individuals.json
[{"id": "SAMPLE001", "sex": null, "ethnicity": null, ...}]
```

Note: `start` uses 0-based coordinates (VCF POS is 1-based, so `start = POS - 1`).

### Step 5: Transform Phenotype Data (Optional)

If you have clinical/phenotype data (CSV/TSV/XLSX):

```bash
beacon python $TOOLS/phenotype_transform/phenotype_to_beacon.py /path/to/phenotypes.csv \
    --output /cbio/users/$USER/beacon_output/phenotype_output \
    --individuals /cbio/users/$USER/beacon_output/vcf_output/individuals.json \
    --config $TOOLS/config/settings.yaml \
    --verbose
```

**Expected input columns (flexible naming):**

| Standard Name | Also Accepts | Required? |
|---|---|---|
| `individual_id` | `sample_id`, `patient_id`, `subject_id` | Yes |
| `phenotype_id` | `hpo_id`, `term_id` | For phenotypes |
| `phenotype_label` | `phenotype_name`, `phenotype` | For phenotypes |
| `disease_id` | `mondo_id`, `ordo_id` | For diseases |
| `disease_label` | `disease_name`, `diagnosis` | For diseases |
| `observed` | `present`, `status` | No (defaults to true) |

The transformer auto-detects column names and normalizes them.

### Step 6: Validate

```bash
# Validate variants (strict mode = stop on first error)
beacon python $TOOLS/validation/validate_json.py \
    /cbio/users/$USER/beacon_output/vcf_output/variants_batch.jsonl \
    --schema-type variant --strict

# Validate individuals
beacon python $TOOLS/validation/validate_json.py \
    /cbio/users/$USER/beacon_output/vcf_output/individuals.json \
    --schema-type individual --strict

# Validate phenotypes (if generated)
beacon python $TOOLS/validation/validate_json.py \
    /cbio/users/$USER/beacon_output/phenotype_output/phenotypes.json \
    --schema-type phenotype --strict
```

**Validation checks:**
- Required fields present (`id`, `assembly_id`, `reference_name`, `start`, `end`, `reference_bases`, `alternate_bases` for variants)
- Correct data types (`start` is integer, `id` is string)
- Value ranges (`start >= 0`, valid chromosome names)

### Step 7: Import to Production MongoDB

MongoDB runs inside Docker on the beacon server (<your-server-ip>). You need an SSH tunnel.

```bash
# Terminal 1 (or use tmux/screen): Create SSH tunnel
ssh -f -N -L 27017:localhost:27017 <your-ssh-alias>

# Verify tunnel is up
nc -z localhost 27017 && echo "Tunnel OK" || echo "Tunnel FAILED"
```

```bash
# Terminal 2: Import data through the tunnel
MONGO_URI="mongodb://localhost:27017/"

# Import variants
beacon python $TOOLS/data_import/import_to_mongo.py \
    /cbio/users/$USER/beacon_output/vcf_output/variants_batch.jsonl \
    --db beacon_db --collection variants \
    --mongo-uri "$MONGO_URI" --verbose

# Import individuals
beacon python $TOOLS/data_import/import_to_mongo.py \
    /cbio/users/$USER/beacon_output/vcf_output/individuals.json \
    --db beacon_db --collection individuals \
    --mongo-uri "$MONGO_URI" --verbose

# Import phenotypes (if available)
beacon python $TOOLS/data_import/import_to_mongo.py \
    /cbio/users/$USER/beacon_output/phenotype_output/phenotypes.json \
    --db beacon_db --collection phenotypes \
    --mongo-uri "$MONGO_URI" --verbose
```

**Alternative: Copy files to beacon server and import locally**

```bash
# From ILIFU compute node:
scp -r /cbio/users/$USER/beacon_output \
    <your-ssh-alias>:~/

# SSH to beacon server:
ssh <your-ssh-alias>

# Import using mongoimport (via Docker)
docker exec -i beacon-mongodb mongoimport \
    --db beacon_db --collection variants \
    --type json --file /dev/stdin < ~/beacon_output/vcf_output/variants_batch.jsonl

docker exec -i beacon-mongodb mongoimport \
    --db beacon_db --collection individuals \
    --type json ~/beacon_output/vcf_output/individuals.json
```

### Step 8: Verify

```bash
# Flush Redis cache (old test data may be cached)
ssh <your-ssh-alias> \
    "docker exec beacon-redis redis-cli FLUSHDB"

# Check datasets endpoint
curl -s "http://<your-server-ip>:8000/api/datasets" | python -m json.tool

# Query a known variant
curl -s "http://<your-server-ip>:8000/api/g_variants?\
assemblyId=GRCh38&referenceName=1&start=100000&\
referenceBases=A&alternateBases=T" | python -m json.tool

# Check variant count in MongoDB
ssh <your-ssh-alias> \
    "docker exec beacon-mongodb mongosh beacon_db --eval 'db.variants.countDocuments({})'"

# Check individual count
ssh <your-ssh-alias> \
    "docker exec beacon-mongodb mongosh beacon_db --eval 'db.individuals.countDocuments({})'"
```

## Performance Tuning

### For Large Datasets (>10M variants)

Edit `config/settings.yaml` or pass `--batch-size` / `--workers` to the pipeline script:

```yaml
processing:
  batch_size: 10000     # Process 10k variants per batch (up from 1000)
  max_workers: 4        # Match your --cpus-per-task SLURM allocation
  memory_limit: 8192    # 8GB per worker
```

### SLURM Resource Requests

```bash
# For large WGS cohort VCFs (100+ samples, 10M+ variants)
srun --pty --nodes=1 --ntasks-per-node=1 --cpus-per-task=8 \
     --mem=64G --time=3-0:0:0 bash

# For smaller exome/panel data
srun --pty --nodes=1 --ntasks-per-node=1 --cpus-per-task=2 \
     --mem=16G --time=1-0:0:0 bash
```

### Using Screen/Tmux for Long Runs

For large datasets that may take hours:

```bash
# Start a tmux session (persists if SSH disconnects)
tmux new -s beacon

# Run pipeline inside tmux
./scripts/run_ilifu_pipeline.sh /path/to/large.vcf.gz

# Detach: Ctrl+B then D
# Re-attach later: tmux attach -t beacon
```

## Troubleshooting

### Common Issues

**`Failed to build 'cyvcf2'` / `No module named 'pkg_resources'` during
`pip install`:**

```text
ModuleNotFoundError: No module named 'pkg_resources'
ERROR: Failed to build 'cyvcf2' when getting requirements to build wheel
```

Fix: you installed `requirements.txt` on Python 3.12. It pins `cyvcf2==0.30.22`,
which has no 3.12 wheel, so pip compiles it in an isolated build environment
whose setuptools no longer ships `pkg_resources`. Pinning `setuptools<70` in
your venv does not help, because pip's build isolation ignores it. Install
`requirements-runtime.txt` from wheels instead, as in Step 2:

```bash
pip install --only-binary=:all: -r requirements-runtime.txt
```

**`File exists: .../afrigend-beacon2-tools/.venv` when creating the venv:**

```text
Error: [Errno 17] File exists: '.../afrigend-beacon2-tools/.venv'
```

Fix: clones made before this was fixed contain a stray `.venv` symlink that
points at a path on a developer's laptop, so it dangles on the cluster. Check
with `ls -l .venv`, then remove only the link with `rm .venv` (no trailing
slash) and create the venv again. Clones made after the fix do not have it.

**`ensurepip is not available` when creating the venv:**

```text
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.12-venv
```

Fix: `apt` is not available to you on the cluster. Remove the half-created
`.venv` and use the `uv` or `--without-pip` method in
[Step 2](#step-2-install-the-tools).

**`cyvcf2` import error:**
```
ModuleNotFoundError: No module named 'cyvcf2'
```
Fix: Ensure the venv is activated (`source .venv/bin/activate`). If `cyvcf2` failed to install, try `pip install --no-cache-dir cyvcf2` or use conda.

**SSH tunnel refused:**
```
ssh: connect to host ... port 22: Connection refused
```
Fix: Verify your SSH config has the `<your-ssh-alias>` alias. Check `~/.ssh/config`.

**MongoDB connection timeout:**
```
pymongo.errors.ServerSelectionTimeoutError
```
Fix: Verify the SSH tunnel is active: `nc -z localhost 27017`. Re-create if needed.

**Validation errors on phenotype data:**
```
Record 42: 'sex' is not one of ['MALE', 'FEMALE', 'OTHER', 'UNKNOWN']
```
Fix: The individual schema expects uppercase sex values. Normalize your input data or adjust the schema.

**Out of memory on compute node:**
Fix: Request more memory (`--mem=64G`) or reduce batch size (`--batch-size 500`).

### Checking Pipeline Output

```bash
# Count lines in variants file
wc -l beacon_output/vcf_output/variants_batch.jsonl

# Peek at first variant
head -1 beacon_output/vcf_output/variants_batch.jsonl | python -m json.tool

# Check transformation summary
cat beacon_output/vcf_output/transformation_summary.json | python -m json.tool
```

## Tool Reference

| Tool | Purpose | Input | Output |
|---|---|---|---|
| `vcf_to_beacon.py` | VCF → Beacon JSON | `.vcf.gz` | `variants_batch.jsonl`, `individuals.json` |
| `phenotype_to_beacon.py` | Phenotypes → Beacon JSON | `.csv`/`.tsv` | `phenotypes.json`, `diseases.json` |
| `validate_json.py` | Validate against schemas | `.json`/`.jsonl` | PASS/FAIL report |
| `import_to_mongo.py` | Import to MongoDB | `.json`/`.jsonl` | Records in MongoDB |
| `export_from_mongo.py` | Export from MongoDB | MongoDB query | `.json` files |

## Verification Checklist

After completing the pipeline, verify:

- [ ] Tools installed and `--help` works
- [ ] VCF transformed without errors (check `transformation_summary.json`)
- [ ] Validation passes in strict mode
- [ ] Data imported to MongoDB (check counts)
- [ ] Beacon API returns results for real variants
- [ ] Frontend displays real datasets (not `[Test]` prefixed)
- [ ] Redis cache flushed
