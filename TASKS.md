# Tasks

Follow-ups that are not in a PR yet. Source for the first block: `docs/audits/2026-10-22-afrigend-beacon-review.md`
(measured against production `v1.1.11`, `f6d5a5a`, 2026-10-22).

## From the 2026-10-22 review

- [ ] **G1, OPEN, wrong YES.** `geneId`, `aminoacidChanges`, `variantMinLength`, `variantMaxLength` and array `start`/`end` are
  silently dropped by `BeaconQuerySerializer`; `geneId=HBB` returns `exists:true, numTotalResults:42331932`. Reject
  unsupported parameters with a 400 (or implement them) and correct `docs/TESTING.md` lines 389 to 413 and 505 to 517. Test:
  `geneId=NOSUCHGENE` must not be a 200 YES. Blocked on: nothing.
- [ ] **G2, OPEN.** The query throttle is 50 per hour per IP, shared with every other API endpoint, and the network's health
  polling (24 per hour) uses about half. Honour `X-Beacon-Aggregator` or give health polling its own budget; read the client
  IP from a trusted proxy hop only. #134 (rate from `RATELIMIT_QUERY_ENDPOINT`) is merged but not deployed. Blocked on:
  deciding the aggregator exemption (the user), then a deploy.
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
