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
- [ ] **G6, OPEN (new 2026-10-23): stale cached answers after a deploy.** The query views sit behind `cache_page(60 * 5)`, so
  for up to 5 minutes after a deploy an identical URL is served from the old release. Measured: the pre-deploy probe
  `geneId=NOSUCHGENE_ZZZ&limit=1` still returned the old 200 YES minutes after v1.1.12 was live, and a fresh URL returned 400.
  Probe a new URL (change `limit` or add `_t`) after any deploy that changes answers; consider clearing the cache in the deploy.
- [ ] **G7, OPEN (new 2026-10-23): spec compliance gaps, read against the Beacon v2 request-parameters schema and the
  docs.genomebeacons.org query table.** (a) A point query with only `referenceName` and `start` is not a defined query type; the
  schema prose says a lone `start` needs `alternateBases`, the docs table asks for both bases. We answer "any variant here"
  without saying so. DECIDED 2026-10-23: keep it, not a 400, because the Beacon Network form (`validators.ts`, alleles
  `.optional()`) and this beacon's own frontend both let users leave alleles blank; it is documented as an extension in
  `docs/SPEC_CONFORMANCE.md`. Still open: have the response say which question was answered (needs a spec-safe place for it). (b) The spec names are `aminoacidChange` (singular)
  and `genomicAlleleShortForm`; both are refused today. (c) done: documented in `docs/SPEC_CONFORMANCE.md` (G3, G4 fixed in the same PR).
- [x] **G3, FIXED in the PR for `docs/beacon-v1.1.12-shipped` (not yet released).** Every error body is a Beacon error
  envelope with `receivedRequestSummary`, including the DRF 429 (`Retry-After` kept) and the rate-limit middleware 429
  (`beacon_api/test_error_envelopes.py`, now in the CI Django step). Still open under G3: `/service-info` equals `/info`,
  and Django HTML 404 for unrouted paths.
- [x] **G4, DONE in the same PR.** `docs/SPEC_CONFORMANCE.md` and the README badge now say 10 of 11 entities valid and list the
  known gaps. EGA verifier re-run on production v1.1.12 on 2026-10-23: 10 valid, `Dataset` failed (five per-dataset routes
  answer 501 by design). Still open: decide whether to keep 501 on those routes.
- [ ] **G5, OPEN, other repo.** `african-beacon-network/backend/fixtures/conformance_known_issues.yaml` baselines AfriGen-D
  failures that no longer occur and would hide a real regression of `/configuration` or `/map`. Delete the stale entries
  (that repo's own rule). Not touched from here.
- [ ] #130 individuals sharing a sample id across datasets replace each other: check the Taine datasets before they are
  loaded together.
- [ ] Re-run the review after the ten Taine population beacons are loaded and registered: not measurable today
  (production holds one dataset, `H3A_V6_AFR`).
- [ ] Stale dependabot PRs #1, #57, #70.
