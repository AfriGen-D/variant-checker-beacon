# AfriGen-D Beacon review, 2026-10-22

Target: `https://beacon.afrigen-d.org/api` (production, release `v1.1.11` = `f6d5a5a`, read from `/api/health`). Code read at
`origin/main` `58cb5e0` (v1.1.11 plus #134, a throttle-rate fix that is not deployed yet). Method follows the sibling review of
the AGVD Beacon (`_beacon-afrigend/agvd-beacon/review-2026-10-22.md`). Read-only GET probes (plus one OPTIONS and one POST in
batch 2), 11:05 to 12:13 SAST, about 90 requests. Raw captures: not committed (scratchpad); commands and outputs are quoted below.

Status labels: FIXED (was a defect, shown fixed), OPEN (reproduced today), UNVERIFIED (not shown either way), SUSPECTED
(inferred from code, not shown on the live host), CLEAN (checked, fine).

## Verdict

This beacon passes where the AGVD Beacon fails on the two answer-correctness defects (H1 coordinates, H2 range upper edge),
on range and gene latency, on the metadata contract (Configuration, EntryTypes, `/filtering_terms`, JSON errors) and on the EGA
verifier (10 of 11 entities valid against 3 of 11). It has its own open defects, ranked:

1. **`geneId` (and other advertised parameters) are silently dropped, so the beacon answers a confident YES to a gene
   question.** `geneId=HBB` returns `exists: true, numTotalResults: 42331932` (the whole panel). Same defect class as AGVD H3,
   but worse: AGVD gives no answer, this beacon gives a wrong one. OPEN.
2. **The query throttle is 50 requests per hour per IP and is shared across all API endpoints, and the network's health
   polling alone uses about half of it.** After about 50 requests my IP got HTTP 429 for 58 minutes. Never fails as a false
   NO (the network sees an error), but it can take the AfriGen-D beacon out of most network searches. OPEN (measured once;
   the shared-history mechanism is read from DRF and the code, SUSPECTED).
3. **The network's conformance baseline for this beacon is stale and would hide a real regression.** OPEN, in the
   `african-beacon-network` repo, not in this one.
4. Smaller spec and documentation gaps (429 body shape, error envelopes without `receivedRequestSummary`, `/service-info`
   equals `/info`, `docs/SPEC_CONFORMANCE.md` says 17/17 and is stale).

Nothing found that makes the network return a wrong NO for a position query.

## Side-by-side with the AGVD findings

AGVD column is from `agvd-beacon/review-2026-10-22.md` and `findings-conformance.md`. This beacon is measured on the date above.

| AGVD finding | AGVD (2026-10-22) | AfriGen-D Beacon | Evidence (this beacon) |
| --- | --- | --- | --- |
| H1 `start` 1-based, confident NO off by one | OPEN | **CLEAN, 0-based** | rs334 11:5227002 (1-based), `start=5227000` false, `5227001` true, `5227002` false; BRCA1 17:43044346, `43044344` false, `43044345` true, `43044346` false. Positive control true in the same run |
| H2 range upper edge false positive | OPEN | **CLEAN** | variant stored `[5227001,5227002)`: `start=5227002&end=5227005` false; `start=5226990&end=5227001` false; `start=5227001&end=5227005` true; `start=5226990&end=5227002` true; 17:`43044346-43044350` false |
| H3 / C5 `geneId` no answer (timeout) | OPEN | **OPEN, different failure**: answers YES for everything | `geneId=HBB&assemblyId=GRCh38&limit=1` 200 in 0.28 s `exists:true, numTotalResults:42331932`; geneId absent from `BeaconQuerySerializer` (`validators.py`), DRF drops unknown fields |
| M1 range latency 9 to 10 s, timeouts | OPEN, erratic | **CLEAN** | 1 kb, 100 kb and 1 Mb ranges 0.27 to 0.29 s each |
| C1 `ontologyTermForThisType` missing | OPEN | **CLEAN** | verifier Configuration and EntryTypes valid; both carry `ENSGLOSSARY:0000092` and `NCIT:C25190` |
| C2 `/filtering_terms` 404 HTML | OPEN | **CLEAN** | 200 JSON envelope, empty list, 0.06 s |
| C3 entity endpoints HTML 404 | OPEN | **mostly CLEAN** | `/datasets`, `/cohorts`, `/biosamples`, `/analyses`, `/runs`, `/individuals` valid in the verifier. Per-dataset sub-endpoints answer 501 by design (`capabilities.py`), which the verifier counts as "did not respond": the one failing entity |
| C4 502 on bad granularity | OPEN | **UNVERIFIED on prod, CLEAN in code** | not sent (brief). `requestedGranularity` is a `ChoiceField` (`validators.py`), so a bad value is a 400 envelope, not an exception |
| C6 unknown filter echoed and ignored | OPEN | **CLEAN** (probed) | `filters.py` rejects every `filters` value with a 400 |
| C7 invalid assembly or chromosome gives 200 NO | OPEN | **CLEAN** (probed) | unknown assembly 400; recognised build with no data (GRCh37) 501 "I cannot answer"; invalid chromosome 400. Omitted `assemblyId` silently defaults to GRCh38 (OPEN nit) |
| C8 malformed JSON stack trace | OPEN | **CLEAN in code** | `ParseError` handled, 400 envelope (#75); not probed |
| C9 400s omit `receivedRequestSummary` | OPEN | **OPEN** | `build_error_envelope` calls `build_meta()` with no request (`utils.py`) |
| C10 weakly filtered query served | SUSPECTED | **CLEAN** | chromosome-only query answers a true YES in 0.28 s, not a capped count |
| C11 auth declared, not enforced | OPEN | **CLEAN** | `securityLevels: ["PUBLIC"]` only, nothing to enforce |
| C15 `Server: nginx/1.10.3`, `environment: staging` | OPEN | **OPEN (banner), CLEAN (environment)** | `Server: nginx/1.10.3 (Ubuntu)` (the UCT front proxy); `environment: "prod"` |
| C16 429 body shape | not exercised | **OPEN, measured** | 429 body `{"detail":"Request was throttled. Expected available in 3480 seconds."}` with `Retry-After: 3480`; the middleware's own 429 is `{"error":..., "message":...}`; neither is a Beacon envelope |
| CORS pinned to own origin | unchanged | **CLEAN** | preflight from the network origin: `access-control-allow-origin: *` |
| EGA verifier | 3 pass, 8 fail | **10 pass, 1 fail** | below |

## Findings

### G1. Parameters that are not in the serializer are dropped, and the answer is a confident YES. FIXED in code 2026-10-23 (not yet released)

Measured: `geneId=HBB&assemblyId=GRCh38&limit=1` gives `exists:true, numTotalResults:42331932`, `resultSets: []`
(`numTotalResults` is the whole catalogue total, `views_boolean.py` `QUERY_UNBOUNDED` branch). `geneId` is not a field of
`BeaconQuerySerializer`, so DRF discards it and the query reduces to the default `assemblyId=GRCh38`. A gene that does not exist is
shown to answer the same (control `geneId=NOSUCHGENE_ZZZ` confirmed: same 200 YES, batch 2).

This is the failure class `beacon_api/filters.py` documents for `filters` ("DRF drops unknown fields ... a YES that means
yes, somewhere in the whole panel"), fixed there and for assembly, variantType and datasetIds, but not for the remaining
parameters that `docs/TESTING.md` (lines 389 to 413, 505 to 517) advertises as supported: `geneId`, `aminoacidChanges`,
`variantMinLength`, `variantMaxLength`, and array-valued `start`/`end`. The network does not send any of them
(`grep` over `african-beacon-network/backend` and `frontend/src`: no matches), so the network is not exposed today; a direct
caller following `docs/TESTING.md` is. Fix: reject any parameter that is neither implemented nor on a short ignore list with a 400,
or implement it; correct `docs/TESTING.md`.

### G2. Throttle: 50 per hour per IP, one shared history across endpoints. Shared history FIXED in code 2026-10-23 (not yet released)

- `QueryRateThrottle` (`views_boolean.py`) is an `AnonRateThrottle` subclass, so it shares the cache key `throttle_anon_<ident>`
  with the default `anon` throttle on every other DRF view. Measured: about 50 accepted requests from my IP (7 metadata,
  the verifier run, 18 `g_variants`) and the next two got 429, `Retry-After: 3480`. Consistent with one shared history;
  not isolated by a controlled test (SUSPECTED mechanism, measured symptom).
- The network checks health every 5 minutes (`african-beacon-network/TASKS.md`, `check_beacons` cron) with `GET /info` and
  `GET /datasets`: 24 requests per hour from one IP, about half of the 50. The rest is what the network's users share.
  `X-Beacon-Aggregator` (sent by `fan_out.py` for exactly this purpose) is not honoured anywhere in `beacon_api/`.
- The 429 is an error to the network (`status: error`), not a false NO, so answers stay honest.
- #134 (merged 2026-10-22, not yet deployed) makes the rate follow `RATELIMIT_QUERY_ENDPOINT`; it does not separate health
  polling from queries or exempt the aggregator.
- Client IP is read from `X-Forwarded-For` (first element in the middleware, the whole header in DRF's default ident).
  A caller can set that header, so the limit is probably bypassable. SUSPECTED from code, not tested (testing would mean
  evading a rate limit on production).

### G3. 429 and error shapes. OPEN (low)

429 bodies are not Beacon envelopes (see C16 row). Error envelopes from `build_error_envelope` carry `meta` without
`receivedRequestSummary` (C9). `/service-info` is byte-identical to `/info` (a Beacon info envelope, not GA4GH
`service-info` with a `type` object). `info.createDateTime` is `2025-08-11`.

### G4. Dataset-scoped routes answer 501 and fail the verifier's `Dataset` entity. OPEN by design

Verifier stderr (this run): `Dataset ✗` with five lines `Endpoint .../datasets/H3A_V6_AFR/{analyses,biosamples,g_variants,individuals,runs}
did not respond`. `capabilities.py` deliberately returns 501 ("I cannot answer", not "no") since #48/#59. The deliberate choice is
right for answer honesty; the cost is a red entity. `docs/SPEC_CONFORMANCE.md` still says "17 PASS / 0 FAIL" (last verified
2026-08-06) and describes these routes as empty-envelope stubs. Stale documentation, OPEN.

### G5. The network's conformance baseline for this beacon is wrong in the safe direction for today and unsafe later. OPEN (other repo)

`african-beacon-network/backend/fixtures/conformance_known_issues.yaml` (last changed 2026-05-03) baselines AfriGen-D failures
for Info, Configuration, BeaconMap, EntryTypes and Genomic Variants ("flat-boolean shape", "/map not implemented upstream").
All of those entities pass today. The patterns include `Endpoint .* did not respond`, so a future outage of `/configuration` or
`/map` would be read as "accepted" and the pre-add gate and the `conformance.yml` workflow would stay green. The file's own rule
is "when upstream fixes an entry, DELETE it". Read from code only; I did not run `verify_beacon` or the workflow.

## EGA beacon-verifier (production, 2026-10-22 11:08 SAST, image `beacon-verifier:latest`)

```text
Valid: Info, Configuration, Beacon Map, Entry Types, Bioinformatics analysis, Biological Sample, Cohort,
       Genomic Variants, Individual, Sequencing run
Failed: Dataset  (5 per-dataset sub-endpoints "did not respond": 501 by design)
```

Compare `docs/verifier/beacon-verifier-2026-08-06.json` (all valid) and the AGVD run (3 valid, 8 failed). The network's required
entities (Configuration, EntryTypes, BeaconMap, Genomic Variants) all pass, so the pre-add gate would pass on the verifier output.

## Network fit (African Beacon Network at `f45c8c3`)

| Behaviour | Result today |
| --- | --- |
| Health `GET /info`, `GET /datasets` | 200 JSON in about 0.06 s; `online` |
| Position query (`start - 1`, `network.ts:23`) | correct: 0-based on both sides |
| Range query (`end` unchanged) | correct at the upper and lower edge, about 0.3 s |
| `requestedGranularity=record`, `includeResultsetResponses=ALL`, aggregator headers, `_t` cache-buster | accepted (unknown keys ignored, harmless) |
| `filters=...` from the network UI | 400 with a clear message: the beacon refuses, the network records `error` for it, not a NO |
| Per-dataset result sets | `resultSets[].id/exists` present for locus queries |
| Rate | see G2: shared 50 per hour, health polling takes about 24 |

The population beacons the Taine project is loading are **not in production**: `/api/datasets` lists one dataset
(`H3A_V6_AFR`, 42,331,932 variants, 1,895 samples) and `/api/info` the same. The ten population builds sit on the dev VM
(`/mnt/impute-storage/workspace/taine/beacon_filtered_data/build/`) and are not loaded into any running Beacon (Taine state
note, 22 Oct 10:15). So their behaviour in the network cannot be measured yet. Code-level points for when they load: variant
`_id` is dataset-scoped since #129 so shared variants keep both copies; per-dataset attribution runs one probe per dataset for
locus queries only (`allows_per_dataset_attribution`), fine for 11 datasets; `import_to_mongo.py` still lets individuals with
the same sample id in two datasets replace each other (#130, OPEN).

## What came back clean

- Point queries (0.27 s warm, 0.08 s cached): positive controls pass at two loci; allele-specific query T>A true.
- `hg38` alias resolves to GRCh38 (true); `chr11` and `11` both match.
- Ranges, including a 1 Mb window without a limit, answer in about 0.3 s (the `BEACON_MAX_VARIANT_SPAN` lower bound).
- Metadata: `/info`, `/configuration`, `/entry_types`, `/map`, `/filtering_terms`, `/datasets` all 200 JSON, each under 0.07 s.
- Repo CI runs backend tests (`ci-cd.yml`): 209 Django-free tests pass locally at `58cb5e0` (`python -m unittest ...`, 0.002 s);
  the 2026-08-13 audit's "CI runs zero backend tests" is FIXED.
- The 2026-08-13 root cause (parameters validated then dropped) is FIXED for `assemblyId`, `variantType`, `datasetIds`,
  `end` without `start`, `filters`, the POST body (#53), and `sex`; G1 is the remainder.

## Instrument notes and disclosure

- My probing used up the per-IP throttle: about 50 requests in 25 minutes, then 429 until 12:10 SAST. The metadata and verifier
  calls count against the same history as `g_variants` (G2). No probe was sent after the first 429 until the window cleared.
  This is exactly the self-inflicted 429 the 2026-08-13 audit warned about.
- First two shell attempts of the point probes sent no request (malformed URL from space-joined arguments); no data discarded.

## Not established

C4 on production (deliberately not sent),
multi-allelic and X/MT sites, MAF values, the network's `verify_beacon` run, behaviour with the Taine datasets loaded,
whether `X-Forwarded-For` spoofing actually bypasses the limit.

## Batch 2 (12:12 to 12:13 SAST, after the throttle cleared; 21 requests, all answered)

| Probe | Result |
| --- | --- |
| rs334 positive control `11&start=5227001` | 200 true (same run as every negative) |
| `geneId=NOSUCHGENE_ZZZ` | 200 `exists:true, numTotalResults:42331932`: **G1 confirmed with a nonexistent gene** |
| `bogusParam=zzz` added to a valid locus | 200 true: any unknown parameter is ignored silently |
| `assemblyId=GRCh37` | 501 "cannot answer ... not a statement about whether the variant exists" (CLEAN) |
| `assemblyId=GRCh99`, `referenceName=99`, `start=abc` | 400 Beacon error envelope each (CLEAN; C7) |
| `filters=GO:0008150` | 400 with a clear message (CLEAN; C6) |
| `end` without `start`; `start=5227010&end=5227001` | 400 each (CLEAN) |
| allele `A>A` at rs334 | 200 false; `variantType=SNP` true; `variantType=DEL` false (filters are applied) |
| `referenceName=1&limit=1` (no position) | 200 true, 0.28 s: a true answer, not a silent cap (C10 not reproduced) |
| `GET /datasets/H3A_V6_AFR/g_variants` | 501 Beacon envelope (by design) |
| `GET /api/nosuchpath` | 404 `text/html` Django page (OPEN, low; AGVD C3 shape for unrouted paths only) |
| `Authorization: Bearer not-a-real-token` | 200, same as anonymous (CLEAN: beacon is PUBLIC only) |
| CORS preflight, Origin `https://beacon-network.afrigen-d.dev` | 200, `access-control-allow-origin: *` (CLEAN; AGVD pins to its own origin) |
| spec-shaped POST (`query.requestParameters`, rs334) | 200 true, `resultSets[0].id H3A_V6_AFR` (CLEAN) |

Errors observed carry no `receivedRequestSummary` (confirms C9) and the 400 bodies are Beacon envelopes.

## Recommended next action

Fix G1 first (reject unsupported parameters with 400, or implement `geneId`): it is the only defect here that gives a caller a
wrong YES. Then G2 (exempt or separate health polling and the aggregator from the query throttle), then clean the network
baseline (G5) and update `docs/SPEC_CONFORMANCE.md` (G4). Do not touch coordinates: they are correct.
