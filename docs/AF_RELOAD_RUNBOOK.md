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

Run the prepared check inside the tools container (no Mongo, no pipeline):

```bash
SIF=$(find /cbio/users/mamana -name 'beacon-tools*.sif' 2>/dev/null | head -1)
singularity exec "$SIF" python /cbio/users/mamana/validate_af_extraction.py
```

Proceed only if it reports `1000/1000 … non-null allele_frequency`.

## Step 1 — Get the fixed transform into the pipeline

The transform is **baked into `beacon-tools.sif`** (`tools_base=/opt/beacon-tools`),
so one of:

- **Rebuild the container** from `nextflow/docker/Dockerfile.tools` with the fixed
  `afrigend-beacon2-tools/vcf_transform/vcf_to_beacon.py`, OR
- **Override `tools_base`** to a `/cbio` checkout that contains the fixed transform
  (works because `singularity.autoMounts = true` bind-mounts `/cbio`). Verify the
  checkout's other tools match the container's expectations.

The fix currently lives only on local branch `feat/allele-frequency` (uncommitted,
entangled with WIP) — land/commit it first so there's a clean source.

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
