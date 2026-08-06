# GA4GH Beacon v2 Spec Conformance

This document tracks the conformance of the AfriGen-D Beacon v2 (boolean
public profile) against the [official GA4GH Beacon v2 specification](https://github.com/ga4gh-beacon/beacon-v2),
verified using the official EGA tooling.

**Last verified:** 2026-08-06
**Endpoint tested:** `https://beacon.afrigen-d.org/api/` (the user-facing
production node; the `api-beacon.afrigen-d.dev` sidecar is equivalent but was
offline 2026-05-07 → 2026-08-06)
**Verifier:** [`EGA-archive/beacon-verifier`](https://github.com/EGA-archive/beacon-verifier)
v0.3.3 (Rust CLI · last upstream update Sep 2025)
**Verdict:** ✅ **17 PASS / 0 FAIL / 0 NO-RESP** (full conformance)

## How to re-run the verifier

The verifier is packaged as a Rust CLI. We use it via a pre-built local
Docker image (Rust toolchain not required on the host).

### Quick run

```bash
docker run --rm beacon-verifier:latest https://beacon.afrigen-d.org/api/ > result.json
```

### Re-build the image (one-time, ~3 min)

If the local image is missing:

```bash
mkdir -p /tmp/bv && cat > /tmp/bv/Dockerfile <<'EOF'
FROM rust:1-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
RUN cargo install beacon-verifier
ENTRYPOINT ["beacon-verifier"]
EOF
docker build -t beacon-verifier:latest /tmp/bv
```

### Other tools considered

| Tool | Status | Notes |
| --- | --- | --- |
| `EGA-archive/beacon-verifier` (Rust CLI) | **In use** | Lightweight, JSON output, last update Sep 2025 |
| `EGA-archive/beacon-verifier-v2` | Available | Heavier — Django + Celery + UI; more recent (Dec 2025) but overkill for one-shot validation |
| `ga4gh-beacon/beacon-verifier` | Stale (2023) | Original GA4GH version; superseded by the EGA forks |

## Current state — 17/17 checks passing

| Entity | Verdict | Endpoints |
| --- | :---: | --- |
| BeaconMap | ✅ | `/api/map` |
| Bioinformatics analysis | ✅ | `/api/analyses` |
| Biological Sample | ✅ | `/api/biosamples` |
| Cohort | ✅ | `/api/cohorts` |
| Configuration | ✅ | `/api/configuration` |
| Dataset | ✅ | `/api/datasets`, `/api/datasets/{id}`, `/api/datasets/{id}/{entry_type}` (×5) |
| EntryTypes | ✅ | `/api/entry_types` |
| Genomic Variants | ✅ | `/api/g_variants` |
| Individual | ✅ | `/api/individuals` |
| Info | ✅ | `/api/info` |
| Sequencing run | ✅ | `/api/runs` |

## Fix history

### 2026-05-02 — initial conformance work

Started at 3/11 PASS. Four fix passes against the verifier yielded full conformance.

**Architectural changes** (`beacon_api/utils.py`):

Added five envelope helpers, all declaring `returnedGranularity: 'boolean'`
in `meta` (the public profile's natural ceiling):

- `build_meta(returned_granularity, received_request=None)` — base meta block.
- `build_received_request_summary()` — fixed shape with empty
  `requestedSchemas: []`. **Does not echo raw request params** (the spec
  requires a structured object whose schema varies per entry type; echoing
  the validated dict failed schema validation).
- `build_info_envelope(payload)` — `{meta, response}` for `/info`,
  `/configuration`, `/map`, `/entry_types`.
- `build_query_envelope(exists, num_total, result_sets, validated_params)` —
  `{meta, responseSummary, response: {resultSets}}` — used for
  `/g_variants`, `/individuals`, and all queryable entry-type lists.
- `build_collection_envelope(items, set_type, set_id)` — alternative
  collection shape; kept for `/filtering_terms` (not validated by the
  verifier) but **not** used for entry types.

**View changes** (`beacon_api/views_boolean.py`):

| Change | Endpoint(s) |
| --- | --- |
| Wrapped flat response in info envelope | `/info` |
| Switched flat dict to query envelope | `/datasets`, `/cohorts`, `/cohorts/<id>` |
| Switched `create_boolean_response` calls to `build_query_envelope` | `/g_variants`, `/query/individuals` |
| Added `name` + `referenceToSchemaDefinition` to `g_variants/defaultSchema` | `/entry_types`, `/configuration` |
| Added 4 stub list endpoints (empty query envelope) | `/individuals`, `/biosamples`, `/analyses`, `/runs` |
| Added 2 dataset-scoped endpoints (single + sub-entity) | `/datasets/<id>`, `/datasets/<id>/<entry_type>` |

**Routing changes** (`beacon_api/urls_boolean.py`):

Registered six new routes. Kept the `query/individuals` alias for legacy
clients.

### Things the verifier surfaced that surprised us

- **The verifier conflates entry-type list endpoints with queries.**
  `/individuals`, `/biosamples`, `/analyses`, `/runs` all need
  `responseSummary` at the top level — same shape as `/g_variants`. Using
  a "collection envelope" (just `{meta, response}`) fails for these.
- **`/map` aliases are ignored.** The spec lets `/map` declare alternative
  URLs per entry type; the verifier hardcodes the path probe. So
  declaring `individuals: /api/query/individuals` in `/map` doesn't
  exempt you from also serving `/api/individuals`.
- **`receivedRequestSummary` requires `requestedSchemas: []`.** Easy to
  miss; not always shown in spec examples.
- **`defaultSchema` schemas are validated for `name + referenceToSchemaDefinition`**
  — both required, both must point to a real spec URL.
  We had `individuals/defaultSchema` correct but `g_variants/defaultSchema`
  abbreviated; sibling-key inconsistency caused two distinct test failures.

### Stub endpoints — what they currently expose

`/individuals`, `/biosamples`, `/analyses`, `/runs` return an empty query
envelope today (`responseSummary: {exists: false, numTotalResults: 0}`,
`response.resultSets: []`). They satisfy the spec verifier and federate
correctly through the African Beacon Network aggregator (it sees us as a
beacon that supports those entry types but currently has zero matching
records).

When real individual/biosample/analysis/run data is available, swap the
stub functions in `views_boolean.py` for real query implementations
without route changes.

### Dataset-scoped routes

`/datasets/<id>` returns the single dataset (or empty envelope on miss).
`/datasets/<id>/<entry_type>` is a generic stub that always returns
empty — it satisfies the verifier's per-dataset entity probe without
implementing the cross-product of (datasets × entry types). Real
dataset-scoped query support is a future enhancement.

## Saved baselines

- `docs/verifier/beacon-verifier-2026-08-06.json` — **17/17 PASS**, the full
  machine-readable verdict against `https://beacon.afrigen-d.org/api/`.

After future fixes, re-run and diff against this baseline.

> Two earlier entries here pointed at `screenshots/beacon-verifier-result-2026-05-02.json`
> and `...-log-2026-05-02.txt`. **Neither file was ever committed**, so the
> original 17/17 claim could not be reproduced from the repository. That is why
> the run above is stored in-tree.

## What the verifier does *not* check

It validates **envelope shape only** — never query semantics. It returned a
clean bill of health throughout the period when this beacon was answering
positional queries off by one base and could not match multi-allelic sites at
all. Treat a green run as "the responses are well-formed", never as "the
answers are correct".

It is also sensitive to latency rather than correctness in one place: between
2026-05 and 2026-08-06 the score was really **16/17**, because an
unparameterized `GET /api/g_variants` scanned all ~42M variants and timed out
(HTTP 504 after ~30s). The check reported `operation timed out`, not a schema
failure. That was fixed by bounding unselective queries; the same request now
returns a valid response in well under a second.

## Related

- The African Beacon Network (ABN) aggregator at `beacon-network-dev.afrigen-d.dev`
  federates over this beacon. Its conformance is downstream of ours —
  if our `/g_variants` returns malformed JSON, ABN merger has to handle
  it. ABN lives in a separate repo (`AfriGen-D/african-beacon-network`,
  cloned locally at `/Users/mamana/projects-uct/_afrigen-d/afrigend-beacon-network/`),
  with its own `docs/SPEC_CONFORMANCE.md`. ABN runs on the same VM as
  this repo's API-only sidecar (`afrigend-beacon-network`), but in a
  different `/opt/afrigend/beacon-network/` working tree.
- Real query metrics (separate from spec conformance) are now captured
  via `QueryLog` model + middleware → MongoDB `query_logs`. See main
  CLAUDE.md "Query Logging" section.
