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
| Container runtime | Singularity/Apptainer on ILIFU, or Docker on a server (Step 2) |
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

## Try It First With the Example Data

The repository comes with a small public data set in `examples/` (nine 1000
Genomes individuals on chromosome 22, 67 KB, plus a made-up phenotype file), so
you can run everything below before using your own files. Once you have the
repository and the container (Step 2), this runs the whole pipeline on it in
seconds, stopping before any database import:

```bash
cd /cbio/users/$USER/variant-checker-beacon
./scripts/run_ilifu_pipeline.sh examples/1000G_chr22_subset.vcf.gz \
    --dataset-file examples/dataset.yaml \
    --phenotypes examples/phenotypes_example.csv \
    --container /cbio/users/$USER/beacon-tools.sif \
    --skip-import
```

A correct run ends with `Total errors: 0` for each of the variant, individual and
phenotype files. The step-by-step guide below uses these same files, so you can
compare every result with what you get. See `examples/README.md` for where the
data comes from.

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

# 4. Describe your dataset: a short file that says what it is called
cd variant-checker-beacon
cat > dataset.yaml <<'EOF'
dataset:
  id: MY_DATASET
  name: My dataset
  description: What this data is.
  assembly: GRCh38
EOF

# 5. Run the pipeline: the tools run from the container, so nothing is installed
./scripts/run_ilifu_pipeline.sh /path/to/your_data.vcf.gz \
    --dataset-file dataset.yaml \
    --container /cbio/users/$USER/beacon-tools.sif
```

`dataset.yaml` is required (or `--dataset-id`, see Step 4). Its `id` is the name
your data is listed under: choose your own, for example `AIBST_EXOMES`. There is
no default, so data is never filed under someone else's dataset by accident.
When the pipeline imports, it also creates the dataset's record from this file,
so the dataset appears in the Beacon's dataset list.

`--container` takes a `.sif` file or a `docker://` URI (run with Singularity or
Apptainer), or a plain Docker image name such as
`ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest` (run with Docker,
on a server or workstation). `--runtime` overrides the choice.

### Pipeline Options

```bash
# With phenotype data
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --dataset-file dataset.yaml \
    --phenotypes /path/to/phenotypes.csv

# Transform + validate only (no MongoDB import)
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --dataset-file dataset.yaml --skip-import

# Custom assembly and output location
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --dataset-file dataset.yaml \
    --assembly GRCh37 \
    --output /scratch3/users/$USER/beacon_output

# Preview what will happen (no execution)
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --dataset-file dataset.yaml --dry-run

# Tune for large datasets
./scripts/run_ilifu_pipeline.sh /path/to/data.vcf.gz \
    --dataset-file dataset.yaml \
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

Then choose how to run the container: Singularity on ILIFU (A1) or Docker on a
server or workstation (A2). Each ends by defining a small shell function
`beacon`, which runs a program inside the container, and the variable `$TOOLS`,
which says where the tools live. Every later step is written with them, so the
commands are the same whichever you choose (a function rather than a variable, so
it behaves the same in bash and zsh). Define them again in each new shell
session, or put the lines in your `~/.bashrc`.

#### The tools run from a container

Nothing to install or reinstall: the image carries Python, every library,
`cyvcf2` and `bcftools`. Use Singularity on ILIFU (A1) or Docker on a server or
workstation where you have it (A2).

##### A1. Singularity/Apptainer (ILIFU)

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

**What the two "every shell session" lines do.** The tools are not installed on
the cluster; `bcftools` and the Python scripts live inside the file
`beacon-tools.sif`, and `singularity exec` runs a command inside it. The first
line creates a shortcut named `beacon` so you do not type that out each time:
`beacon bcftools --version` means `singularity exec --bind /cbio,/scratch3
beacon-tools.sif bcftools --version` (`--bind` makes `/cbio` and `/scratch3`
visible inside, so the tools can read your VCFs and write their output, and
`"$@"` stands for whatever you type after `beacon`). The second line,
`TOOLS=/opt/beacon-tools`, stores the folder inside the container where the
scripts are, which keeps later commands short. Both are forgotten when you log
out or start a new `srun`, so paste them again at the start of each session, or
add them to your `~/.bashrc` to do it automatically.

##### A2. Docker

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

##### A3. Build the image yourself

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

### Step 3: Locate Your VCF Files

The commands below use the example data. To use your own files instead, change
the three variables.

```bash
cd /cbio/users/$USER/variant-checker-beacon
VCF=$PWD/examples/1000G_chr22_subset.vcf.gz          # your VCF: /path/to/your_data.vcf.gz
PHENOTYPES=$PWD/examples/phenotypes_example.csv      # your phenotypes (optional)
DATASET=$PWD/examples/dataset.yaml                   # your dataset description
```

```bash
# Your workspace on ILIFU:
ls /cbio/users/$USER/

# Search for VCF files
find /cbio/dbs/ -name "*.vcf.gz" -type f 2>/dev/null | head -20
find /cbio/projects/ -name "*.vcf.gz" -type f 2>/dev/null | head -20

# Check a VCF file header to confirm assembly and samples.
# bcftools is inside the container.
beacon bcftools view -h $VCF | head -30
beacon bcftools query -l $VCF | wc -l   # count samples (example: 9)
```

**Use bcftools to inspect and prepare the VCF before transforming it.** It is
far faster than Python on large files, and a small test slice lets you check the
whole pipeline in minutes before committing to a full run:

```bash
# Contigs the file uses, with their variant counts (needs a .tbi/.csi index)
beacon bcftools index -s $VCF     # example: chr22 and 4231 variants

# Create the index if the file has none
beacon bcftools index -t $VCF

# A small test slice: one region, PASS variants only, compressed and indexed.
# Use the contig name exactly as `index -s` printed it above (this file uses
# chr22; some files use 22).
beacon bcftools view -f PASS -r chr22:16000000-17000000 $VCF \
    -Oz -o /cbio/users/$USER/test_slice.vcf.gz
beacon bcftools index -t /cbio/users/$USER/test_slice.vcf.gz
```

### Step 4: Transform VCF to Beacon JSON

First describe the dataset in a small file, `dataset.yaml`; the example data
comes with one (`examples/dataset.yaml`, id `EXAMPLE_1000G_CHR22`). Only `id` and
`name` are required; unknown keys are refused so a typo cannot be ignored:

```yaml
dataset:
  id: MY_DATASET                 # letters, digits, _ . -  (up to 64)
  name: My dataset
  description: What this data is.
  assembly: GRCh38
  contact:
    name: Your Name
    email: you@example.org
```

```bash
beacon python $TOOLS/vcf_transform/vcf_to_beacon.py $VCF \
    --output /cbio/users/$USER/beacon_output/vcf_output \
    --assembly GRCh38 \
    --dataset-id EXAMPLE_1000G_CHR22 \
    --config $TOOLS/config/settings.yaml \
    --verbose
```

`--dataset-id` attributes every variant to a dataset: use the `id` from your
`dataset.yaml`. Without it the records carry an empty `dataset_ids`, so no
dataset lists them and dataset-scoped queries do not find them; the tool prints
a warning if you leave it out. `run_ilifu_pipeline.sh` instead takes
`--dataset-file dataset.yaml` and reads the id from it (`--dataset-id` also
works there, and must match the file if you give both).

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
beacon python $TOOLS/phenotype_transform/phenotype_to_beacon.py $PHENOTYPES \
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

**Do not import the example data into a production Beacon.** The phenotypes are
made up. To practise this step, use a development Beacon, or stop after Step 6.

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

Importing variants does not create the dataset's record, so it would not appear
in the Beacon's dataset list. Register it from the same `dataset.yaml`, after
the variants are in (`--samples` is the number of samples in the VCF). It
refuses an id that no imported variant carries, and running it again updates the
same record:

```bash
beacon python $TOOLS/data_import/register_dataset.py $DATASET \
    --db beacon_db --mongo-uri "$MONGO_URI" --samples 9
```

`run_ilifu_pipeline.sh` does this for you when you give it `--dataset-file`.

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
./scripts/run_ilifu_pipeline.sh /path/to/large.vcf.gz \
    --dataset-file dataset.yaml

# Detach: Ctrl+B then D
# Re-attach later: tmux attach -t beacon
```

## Troubleshooting

### Common Issues

**`singularity: command not found`:** `singularity` is on the path only in a login
shell on a compute node. Work inside your `srun` session; if you run a single
command over `ssh`, wrap it as `ssh <node> 'bash -lc "<command>"'`.

**`INFO: Mounting image with FUSE.` before every output:** harmless. It is
Singularity saying how it opened the image, and does not mean anything failed.

**`FATAL: ... invalid tar header` from `singularity build`:** the Docker archive
was gzipped. Save it as a plain `.tar` (`docker save -o beacon-tools.tar ...`),
as in A3.

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
