# Allele Frequency (AF) — Reload Runbook

How to populate `allele_frequency` in the deployed `beacon_db.variants` so the
beacon serves AF at `aggregated` granularity. The API + frontend already support
it (branch `feat/allele-frequency`); this runbook is only the **data reload**.

## Why this is needed

The deployed `variants` collection has `annotations: []` and no `allele_frequency`
because the old `vcf_to_beacon.py` used `'AF' in info` / `info[field]` on a cyvcf2
`INFO` object (not a dict) and silently extracted nothing. The source panel VCFs
**do** carry AF (verified 2026-06-17: `##INFO=<ID=AF,Number=A,Type=Float>`
declared; `AF=0.00316623` in data). The fix uses `variant.INFO.get('AF')` with
multi-allelic tuple handling. No `bcftools +fill-tags` recompute is required.

## Source data

`/cbio/dbs/refpanels/h3a_reference_panels/version_6/v6hc_s_african/V6HC-S_AFR/vcfs/`
— `V6HC-S_AFR_chr{1..22}_all.vcf.gz` (~354 GB, 22 autosomes, GRCh38, ~42.3M variants).

## Step 0 — Validate the fix on real data (gate)

Run the check inside the tools container (no Mongo, no pipeline). It calls the
transformer's own extraction, so it tests the code that will actually run:

```bash
cd /cbio/users/$USER
singularity pull --force beacon-tools.sif docker://ghcr.io/afrigen-d/variant-checker-beacon/beacon-tools:latest
VCF=/cbio/dbs/refpanels/h3a_reference_panels/version_6/v6hc_s_african/V6HC-S_AFR/vcfs/V6HC-S_AFR_chr1_all.vcf.gz
singularity exec --bind /cbio beacon-tools.sif \
    python /opt/beacon-tools/validation/validate_af_extraction.py "$VCF"
```

Proceed only if it reports `1000/1000 … non-null allele_frequency` and `PASS`
(exit status 0). It exits 1 if any record lacks a frequency, or if it read no
records at all.

## Step 1 — Get the fixed transform into the pipeline

The transform is **baked into `beacon-tools.sif`** (`tools_base=/opt/beacon-tools`).
The allele-frequency fix is on `main` (merged in #14, 2026-08-05) and in the
published image, so there is nothing to rebuild: the `singularity pull --force`
in Step 0 already fetched it. To use a different build instead, one of:

- **Build the image yourself** from `nextflow/docker/Dockerfile.tools`
  (see Option A3 in `docs/ILIFU_DATA_LOADING_GUIDE.md`), OR
- **Override `tools_base`** to a `/cbio` checkout that contains the transform
  (works because `singularity.autoMounts = true` bind-mounts `/cbio`). Verify the
  checkout's other tools match the container's expectations.

## Step 2 — Single-chromosome dry run (transform only, no Mongo)

Smallest autosome (chr22) with `skip_import: true`; params set
`vcf_file=.../V6HC-S_AFR_chr22_all.vcf.gz`. Verify the emitted
`variants_batch.jsonl` contains `"allele_frequency"` on records.

## Step 3 — Single-chromosome import to a STAGING db (not prod)

Set `mongo_db` to a staging name (e.g. `beacon_db_staging`),
`clear_before_import:false`, import chr22, then point a local API at it and confirm:

```bash
curl '.../api/g_variants?referenceName=22&start=<known>&requestedGranularity=aggregated'
# expect returnedGranularity:"aggregated" + frequencyInPopulations with alleleFrequency
```

## Step 4 — Full reload (DESTRUCTIVE — explicit approval required)

**Resolved topology**: `nextflow/ILIFU/beacon.sh` runs as an `sbatch` job that opens
an SSH tunnel to the prod beacon host (`H3ABN-Beacon_…` = afrigend-beacon-prod),
`localhost:27018 → prod localhost:27017`, and the pipeline loads **directly into
the production `beacon_db`** over that tunnel. There is no staging step.

**Outage risk — do NOT run the naive reload against prod.** `clear_before_import:
true` drops the `variants` collection at the *start*, and the load runs for hours
to days (`--time=7-00:00:00`). That means prod would return "not found" for every
query for the entire load — an extended outage of the core function.

Use a **zero-downtime swap** instead:

1. `mongodump` the current `variants` collection first (rollback).
2. Load into a **new collection** (e.g. `variants_af`) with `clear_before_import:false`
   — the live `variants` keeps serving throughout.
3. Verify the new collection (counts, spot-check AF on a few known variants).
4. Atomically swap: `db.variants.renameCollection("variants_old", true)` then
   `db.variants_af.renameCollection("variants", true)` — seconds of downtime.
5. Flush Redis (Step 5); drop `variants_old` once verified.

(The pipeline imports to the `variants` collection by default, so step 2 needs a
collection-name override or a post-load rename of the freshly-loaded data.)

Run all 22 chromosomes (`vcf_files` glob).

## Step 5 — Post-reload verification (prod)

1. Flush Redis on prod (cached boolean responses): `redis-cli FLUSHDB`.
2. `curl '.../api/g_variants?referenceName=1&start=<known>&requestedGranularity=aggregated'`
   → expect `frequencyInPopulations` with a real `alleleFrequency`.
3. Visually confirm `AF <value>` next to the YES badge in the UI.
4. Re-run `beacon-verifier` against prod — must stay green (default boolean path
   unchanged; aggregated declares its schema).

## Rollback

`mongorestore` the pre-reload `mongodump`. Until the reload completes, queries
return `boolean` (the API degrades gracefully when `allele_frequency` is null).

## Open items

- Commit the AF feature cleanly (currently entangled with WIP across utils.py,
  views_boolean.py, types.ts, DatasetResults.tsx, beacon.ts).
- Confirm the prod load topology (Step 4) before the destructive run.
