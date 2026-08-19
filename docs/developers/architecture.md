# Architecture

How a query becomes an answer. Read this before changing query behaviour.

## Runtime shape

```text
nginx (production TLS, rate limiting)
  ├── /        → frontend container :3000   Next.js 14
  └── /api/*   → beacon-api container :8000 Django + DRF
                        ├── MongoDB :27017  variants, individuals, datasets, query_logs
                        └── Redis   :6379   response cache, throttle counters
```

The UI and API are served from one origin, so a browser query reaches the API
without a cross-origin round trip.

## The path of a variant query

`GET /api/g_variants?assemblyId=GRCh38&referenceName=1&start=42497823`

1. **Throttling** — `views_boolean.py` applies a DRF throttle. Two limiters
   exist and have historically shared a cache scope, which has caused real
   lockouts. Check both before diagnosing a 429.
2. **Parameter extraction** — `views_boolean.py:94-97`. GET reads
   `request.GET.dict()` (flat strings); POST takes `request.data` (nested).
   That asymmetry is the cause of the current POST 400 bug.
3. **Validation and sanitisation** — `validate_query_request` in
   `validators.py`. Rejects filters and pagination *before* sanitising, because
   the sanitiser stringifies values and would otherwise reject spec-shaped
   input for containing quotes it introduced itself.
4. **Mongo query construction** — `views_boolean.py:114-160`. This is where
   correctness lives:
   - chromosome matched as both `1` and `chr1`
   - position built by `build_position_filter` in `query_semantics.py` —
     half-open overlap, with a lower bound so the query can use the index
   - assembly matched (see the vocabulary note below)
   - `referenceBases` / `alternateBases` matched exactly
5. **Cost classification** — `query_cost.py` decides a time budget and whether
   per-dataset attribution is affordable. Its comments record the 30.7-second
   HTTP 504 incident that motivated it.
6. **Execution** against MongoDB, bounded by `max_time_ms`.
7. **Envelope construction** — helpers in `utils.py` build the spec-shaped
   response. Allele frequency, if published, passes through
   `privacy.publish_allele_frequency`, which rounds and applies a minimum
   publishable floor.
8. **Audit** — `QueryLogMiddleware` records the query with the client IP
   truncated to a /24 and a TTL on the row.

## Where the bugs live

Every confirmed correctness defect in this codebase is in step 3 or 4, and all
have the same shape: **a parameter is accepted, validated, and then not
applied.** The query runs anyway and returns 200.

Fixed instance: assembly spellings, now canonicalised in `assembly.py`.
Still open: `variantType`
and `datasetIds` dropped, `end` without `start` widening to chromosome-wide, an
unrecognised `sex` dropped.

`beacon_api/filters.py` is the counter-example and the standard to hold to. It
refuses the `filters` parameter rather than ignoring it, and its docstring
states the reason: a YES meaning "yes, somewhere in the whole panel" is
indistinguishable from "yes, in the cohort you asked about". Apply that
judgement to anything you add.

## Modules worth reading first

| Module | Why |
| --- | --- |
| `query_semantics.py` | Coordinate overlap. The best code in the repo; read the docstring. |
| `filters.py` | The refuse-don't-widen principle, argued in prose. |
| `query_cost.py` | Query budgets, with the incident that caused them. |
| `privacy.py` | AF suppression and IP truncation, with the re-identification reasoning. |
| `assembly.py` | Assembly vocabulary canonicalisation. |
| `validators.py` | Input validation. Also where the POST sanitiser bug lives. |

These carry real post-mortems in their comments. They are the fastest way to
understand why the code is shaped as it is.

## Data model

`Variant` documents hold `assembly_id`, `reference_name`, `start`, `end`,
`reference_bases`, `alternate_bases`, `dataset_ids`, `allele_frequency` and
`annotations`. Coordinates are 0-based half-open. `dataset_ids` is a list, which
is how per-dataset attribution works — and why an importer that replaces rather
than merges it will silently strip attribution when a second panel loads.

## Two deployments

Production runs the **Boolean** stack. A second host runs an API-only sidecar.
The two are not identical — notably their Mongo authentication configuration
differs — so never rsync configuration between them. See `CLAUDE.md`.
