# Tasks

Follow-ups that are not in a PR yet. Source for the first block: `docs/audits/2026-10-22-afrigend-beacon-review.md`
(measured against production `v1.1.11`, `f6d5a5a`, 2026-10-22).

## From the 2026-10-22 review

- [x] **G1, SHIPPED AND VERIFIED ON PRODUCTION in v1.1.12 (tag on e6c1a67, 2026-10-23 15:05 SAST).** `geneId`,
  `aminoacidChanges`, `variantMinLength`, `variantMaxLength`, array `start`/`end` and any unknown parameter give a 400 Beacon
  envelope naming the parameter (`beacon_api/unsupported_params.py`); `/individuals` too. Production, read after the deploy:
  `geneId=NOSUCHGENE_ZZZ&limit=2` 400, `geneId=HBB` 400, `bogusParam` on a valid locus 400, `individuals?sex=MALE&geneId=HBB`
  400; rs334 11:5227001 still true, 5227000 false, T>A true, T>A with `variantType=DEL` false. Not changed: the list endpoints
  (`/datasets`, `/cohorts`, `/filtering_terms`) ignore unknown names but make no YES/NO claim.
- [x] **G2, SHIPPED in v1.1.12: the shared history is confirmed, not suspected.** `QueryRateThrottle` has its own cache scope
  (`query`), so `/info` and `/datasets` polling no longer spends the `g_variants` budget. `X-Beacon-Aggregator` is deliberately
  not an exemption (any caller can send it). Still open: the 50 per hour per IP default, and `X-Forwarded-For` trust (untested).
  Raising the rate is a config choice (`RATELIMIT_QUERY_ENDPOINT`, #134).
- [x] **G6, SHIPPED in v1.1.14, CONFIRMED LIVE 2026-11-17 (raised 2026-10-23): stale cached answers after a deploy.** Also noted: the first v1.1.13 deploy failed in the
  `validate` job (the deploy workflow installed Django without DRF, which the middleware now imports; fixed in PR 138, the gate
  stopped it before anything was built or deployed). The query views sit behind `cache_page(60 * 5)`, so
  for up to 5 minutes after a deploy an identical URL is served from the old release. Measured: the pre-deploy probe
  `geneId=NOSUCHGENE_ZZZ&limit=1` still returned the old 200 YES minutes after v1.1.12 was live, and a fresh URL returned 400.
  Probe a new URL (change `limit` or add `_t`) after any deploy that changes answers; consider clearing the cache in the deploy.
  FIXED (PR 140, b73a55a, an ancestor of v1.1.14): the Redis `KEY_PREFIX` is now `beacon_boolean:<BEACON_RELEASE>` (`cache_key_prefix` in
  `beacon_api/release.py`), so a new release never reads the previous release's cached answers. Read on production 2026-11-17
  (`redis-cli --scan` on `beacon-redis`): keys are `beacon_boolean:v1.1.14:1:...`, matching `/api/health` release v1.1.14. NOT done: the
  same-URL before/after probe across a deploy (it needs the next tag; the key names show the prefix is in effect).
- [ ] **G7, OPEN (new 2026-10-23): spec compliance gaps, read against the Beacon v2 request-parameters schema and the
  docs.genomebeacons.org query table.** (a) A point query with only `referenceName` and `start` is not a defined query type; the
  schema prose says a lone `start` needs `alternateBases`, the docs table asks for both bases. We answer "any variant here"
  without saying so. DECIDED 2026-10-23: keep it, not a 400, because the Beacon Network form (`validators.ts`, alleles
  `.optional()`) and this beacon's own frontend both let users leave alleles blank; it is documented as an extension in
  `docs/SPEC_CONFORMANCE.md`. Still open: have the response say which question was answered (needs a spec-safe place for it). (b) The spec names are `aminoacidChange` (singular)
  and `genomicAlleleShortForm`; both are refused today. Assessed 2026-10-27: `aminoacidChange` stays a 400 by design
  (variants carry no protein annotation, see `beacon_api/unsupported_params.py`). Only `genomicAlleleShortForm` is
  implementable: it needs an HGVS g. parser plus RefSeq accession to assembly mapping (NC_000011.10 is GRCh38, .9 is
  GRCh37) and HGVS 1-based to stored 0-based conversion, with a positive control (rs334, 11:5227002 T>A) before shipping. IN PR from branch `docs/g6-merged-status` (backed up to origin 2026-11-17, was local only for three weeks): parser 6a3ebde and
  `expand_genomic_allele_short_form` e60bd80 in `beacon_api/hgvs.py` (15 tests, both guards mutation-checked). Wired into
  `g_variants` in `views_boolean.py` before `validate_query_request` (HgvsError is a 400). NOT done: verify
  `genomicAlleleShortForm=NC_000011.10:g.5227002T>A` is true and `...5227001T>A` false on dev (no Django locally). (c) done: documented in `docs/SPEC_CONFORMANCE.md` (G3, G4 fixed in the same PR).
- [x] **G3, SHIPPED AND VERIFIED ON PRODUCTION in v1.1.13 (tag on ecfd970, deployed 2026-10-23 16:09 SAST, run 39966231941,
  about 6.9 minutes).** Every error body is a Beacon error envelope with `receivedRequestSummary`. Production, fresh URLs:
  400 (`geneId`, unknown parameter) and 405 (`POST /info`) all return `{meta, error}` with `apiVersion`, `requestedGranularity`,
  `requestedSchemas` and `pagination` in the summary; rs334 11:5227001 true, 5227000 false. NOT exercised on production: a real
  429 (it would lock the tester's IP out of `g_variants` for an hour); the 429 bodies are covered by
  `beacon_api/test_error_envelopes.py` (DRF throttle with `Retry-After`, and the rate-limit middleware). Still open under G3:
  `/service-info` equals `/info` (FIXED IN BRANCH `feat/ga4gh-service-info`, `beacon_api/service_info.py`, 7 tests, not yet in a PR), and Django HTML 404 for unrouted paths.
- [x] **G4, DONE (PR 137, in v1.1.13).** `docs/SPEC_CONFORMANCE.md` and the README badge now say 10 of 11 entities valid and list the
  known gaps. EGA verifier re-run on production v1.1.12 on 2026-10-23: 10 valid, `Dataset` failed (five per-dataset routes
  answer 501 by design). Still open: decide whether to keep 501 on those routes.
- [ ] **G8, OPEN, DECISION CONFLICT (new 2026-10-27, from the network's admission gate).** The network's behavioural verifier
  (`african-beacon-network` `behaviour_checks.py:257`, `params:missing-start`) expects HTTP 400 for a query with no `start`; this
  beacon answers a true YES (G7a, decided 2026-10-23 to keep it because both frontends allow blank alleles/position). Today this
  beacon would FAIL the network's gate (network TASKS.md line 37). Options: (a) 400 on a locus query with `referenceName` and
  no `start` (spec-strict, breaks chromosome-only checks the UI may use), (b) keep and have the network baseline it. Blocked on:
  the user, because it reverses the 2026-10-23 decision. Recommendation: (b) is the lesser change, (a) is spec-strict; confirm
  no frontend path sends a start-less query first (`grep -rn referenceName frontend/src`).
- [ ] **COVERAGE, CODE LIVE IN v1.1.14, DATA NOT POPULATED (user said go 2026-10-27; PR 141, 0770c83, an ancestor of v1.1.14).** `/api/datasets` entries carry `coverage` (chromosomes held, `alleleFrequency` bool) once stored; absent until then. Read on production 2026-11-17: release v1.1.14, and `GET /api/datasets` shows NO `coverage` key on `H3A_V6_AFR`, as expected before the command runs. Code: `describe_coverage` (`capabilities.py`, 5 tests), `Dataset.coverage`, `manage.py compute_coverage`. Shape agreed with the Beacon Network session 2026-11-17 (`{chromosomes: [...], alleleFrequency: bool}`, key absent when unknown; the network treats absent as "unknown", never "not covered"). NOT done: running it on production (a write to the `datasets` document, the user names it; dry run first: `docker exec beacon-api-boolean python manage.py compute_coverage --settings=beacon_project.settings_boolean`; the v1.1.14 build has NO time cap, so with no stored frequency its frequency check scans all 42M documents on the live database, found 2026-11-17 when the dry run was started and ran for minutes; the cap is in PR 148, `--max-time-seconds`, default 60, a timeout aborts with nothing written, and `--max-time-seconds 1` is the positive control that the cap bites), the UI "not covered" state and tile (frontend reads `coverage`), the network showing it per member (network session). View wiring is not unit-tested (no Django locally); verify on production after the command runs.
- [ ] **UI IDEAS from CRG's RNA-Get Beacon Explore page (2026-11-17, from a screenshot only; not tested against their API).** Adopt in this order: (1) three-state result cell with a hatched "not covered" state, fed by `coverage` (above); (2) a persistent "API call" bar showing the exact Beacon request behind a view (today only a copy-curl button on results, `DatasetResults.tsx`); (3) a variant x dataset grid with `n=` sample counts in the column headers and rows paged 5 at a time (one request per row: a locus query already returns every dataset in `resultSets`; worth it once the ten Taine datasets are loaded, today there is one). Skip their chip filter bar and facet pills: the API refuses `geneId` and other filters (G1), so those controls would mislead. The same grid belongs in the Network UI (it already has `PeerRow` and `CoverageMatrix` for the honest states); the Network session was told and has not started anything. MOCKUP DONE 2026-11-17 (canvas https://claude.ai/artifact/PphM8HwnuhcRVhHT2oQiCZ, copy in `docs/design/2026-11-17-result-cell-and-api-bar/`, four cell states incl. "No, unchecked" for a missing `coverage` key). NEXT: the React version of the cell and the API bar in `frontend/src/components/results/`; the cell can ship before `compute_coverage` runs (it then reads "No, unchecked"), the "Not covered" text needs the production run. Not started.
- [ ] **ALLELE-FREQUENCY BEACON (asked 2026-11-17).** The code path is complete: the transformer extracts per-ALT AF (`afrigend-beacon2-tools/vcf_transform/vcf_to_beacon.py:518`), `views_boolean.py` publishes `frequencyInPopulations` at `aggregated` or `record` granularity on locus queries through `publish_allele_frequency` (3 decimals, suppressed below 0.01 = about 38 alleles at 1,895 samples). THE DATA IS THE GAP. Read on production 2026-11-17 (read-only, shell in `beacon-api-boolean`): the stored rs334 document (`chr11`, start 5227001, T>A, `dataset_ids ['H3A_V6_AFR']`) has `allele_frequency = None`, and both `aggregated` and `record` queries for rs334 return no frequency. Other documents not read. Steps: (1) validate the transformer on one chromosome of V6HC-S_AFR with `afrigend-beacon2-tools/validation/validate_af_extraction.py` on an ILIFU compute node (never the login node) and compare rs334 against `bcftools`; (2) fill production: a Nextflow reload or an update-only pass, a production data write the user names, on the user's SLURM allocation; (3) run `compute_coverage` so `coverage.alleleFrequency` becomes true; (4) before the ten Taine population datasets load, derive the publication floor per dataset from its 2N (the 0.01 floor was set for 1,895 samples; the code comment in `privacy.py` says a smaller cohort needs symmetric suppression); (5) let clients tell "not reported" from "withheld below the floor" (both omit the field today): add the floor to the `coverage` block, which is a shape change to ask the network session about first; (6) UI: AF line in the cell and a per-population AF grid, as in the mockup. NOT done: all of it.
- [ ] **G5, OPEN, other repo.** `african-beacon-network/backend/fixtures/conformance_known_issues.yaml` baselines AfriGen-D
  failures that no longer occur and would hide a real regression of `/configuration` or `/map`. Delete the stale entries
  (that repo's own rule). Not touched from here.
- [ ] #130 individuals sharing a sample id across datasets replace each other: check the Taine datasets before they are
  loaded together.
- [ ] Re-run the review after the ten Taine population beacons are loaded and registered: not measurable today
  (production holds one dataset, `H3A_V6_AFR`).
- [ ] Stale dependabot PRs #1, #57, #70.
- [x] **GTM tag GTM-NZ5LBJLV: DONE, LIVE ON PROD v1.1.14 (2026-11-16 20:15 SAST).** `/api/health` reports release v1.1.14; beacon-frontend runs image v1.1.14; the home page references `gtm.js?id=GTM-NZ5LBJLV`. Still open: confirm hits in GA Realtime (needs a GA login); strip the variant query string from `page_location` in GTM/GA4; consent banner decision (POPIA/GDPR). `nginx-docker.conf` is untracked and public responses carry no CSP (docs in #143).
