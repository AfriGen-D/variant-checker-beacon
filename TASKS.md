# Tasks

Follow-ups that are not in a PR yet. Source for the first block: `docs/audits/2026-10-22-afrigend-beacon-review.md`
(measured against production `v1.1.11`, `f6d5a5a`, 2026-10-22).

## From the 2026-10-22 review

- [x] **G1, FIXED in the PR for `fix/beacon-reject-unsupported-params` (not yet released).** `geneId`, `aminoacidChanges`,
  `variantMinLength`, `variantMaxLength`, array `start`/`end` and any unknown parameter now give a 400 Beacon envelope naming
  the parameter (`beacon_api/unsupported_params.py`). Sweep: the same drop existed on `/individuals` (`individual_query_boolean`
  read only `sex` and `diseaseCode`); fixed the same way. Left as is: the list endpoints (`/datasets`, `/cohorts`,
  `/filtering_terms`), which ignore unknown parameters but make no YES/NO claim. `docs/TESTING.md` corrected. Needs a tag
  and deploy (the user names it); after deploy, probe `geneId=NOSUCHGENE_ZZZ` on production, expect 400.
- [x] **G2, FIXED in the same PR (not yet released): the shared history is confirmed, not suspected.** `QueryRateThrottle`
  now has its own cache scope (`query`), so metadata and health polling (`/info`, `/datasets`) no longer spend the
  `g_variants` budget (test: spending the anon budget leaves the query budget whole). `X-Beacon-Aggregator` is deliberately
  not used for an exemption, because any caller can send it. Still open: the 50 per hour per IP default is low for the
  network's users, and `X-Forwarded-For` spoofing is untested. Raising it is a config choice (`RATELIMIT_QUERY_ENDPOINT`, #134)
  for the user. Blocked on: a tag and deploy.
- [ ] **G3, OPEN (low).** 429 bodies and error envelopes: 429 should be a Beacon error envelope; `build_error_envelope`
  should carry `receivedRequestSummary`; `/service-info` should be GA4GH service-info.
- [ ] **G4, OPEN (docs).** `docs/SPEC_CONFORMANCE.md` says 17 of 17; the verifier now gives 10 valid, 1 failed (`Dataset`,
  five per-dataset routes answer 501 by design). Update the document, and decide whether to keep 501.
- [ ] **G5, OPEN, other repo.** `african-beacon-network/backend/fixtures/conformance_known_issues.yaml` baselines AfriGen-D
  failures that no longer occur and would hide a real regression of `/configuration` or `/map`. Delete the stale entries
  (that repo's own rule). Not touched from here.
- [ ] #130 individuals sharing a sample id across datasets replace each other: check the Taine datasets before they are
  loaded together.
- [ ] Re-run the review after the ten Taine population beacons are loaded and registered: not measurable today
  (production holds one dataset, `H3A_V6_AFR`).
- [ ] Stale dependabot PRs #1, #57, #70.
