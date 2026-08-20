# Beacon release and upgrade process — design

Date: 2026-08-19
Status: proposed

## Problem

Three deployments run this beacon, and on 2026-08-19 all three were behind
`main` with no instrument reporting it.

| Instance | Running | Behind `main` |
| --- | --- | --- |
| `beacon.afrigen-d.org` (prod) | `v1.1.4` | 9 commits |
| `api-beacon.afrigen-d.dev` (sidecar) | not reportable | unmeasurable |
| `beacon.ardi.africa` (ARDI) | May 2026 code | ~3.5 months |

Each drift was found by accident, and each cost something real:

- **ARDI** still runs the pre-PR#13 rate limiter, so it 429s our aggregator's
  metadata polls indefinitely. The Beacon Network has been unable to refresh its
  datasets ever since. Found only because someone probed it by hand.
- **Prod** has never received `v1.1.5` (six merged UI changes) or the three
  commits after it — including #44, the `hg38`/`GRCh38` canonicalisation fix.
  Until it ships, production answers `hg38` queries with a confident
  `exists: false` for variants it holds.

### Why nothing caught it

**No instance reports which code it runs.** `/api/health` returns the GA4GH
*spec* version — a constant — so prod and a 3.5-month-old ARDI return the
identical string:

```text
prod    {"version": "2.0.0-boolean", ...}
ARDI    {"version": "2.0.0-boolean", ...}
```

An instrument that returns the same answer for inputs that should differ is not
reporting. Every other part of a release process — drift detection, upgrade
verification, "is ARDI current?" — is unmeasurable until this is fixed.

**Tagging deliberately does not deploy.** `deploy.yml` is `workflow_dispatch`
only, because the first tag-triggered run deployed unattended and took
production down (2026-08-05, see `reference_deploy_pipelines`). That fix was
correct. But removing the automatic trigger without adding a "what is tagged and
unshipped?" signal converted a reliability problem into a silent-staleness
problem. All three drifts descend from that trade.

**A cleanup step paints good deploys red.** The 2026-08-07 run is marked
`failure`; every job succeeded except `cleanup`. A non-essential post-step that
can fail the run makes a successful deploy indistinguishable from a broken one,
and trains readers to ignore reds.

## Goals

1. Any instance can be asked what release it runs, over plain HTTP.
2. One upgrade path, used by both the maintainers and external operators.
3. Drift is reported by a standing check, not discovered by accident.
4. Nothing in the process requires an operator to reconcile a divergent git tree.

## Non-goals

- Fixing ARDI's rate limiter, or the aggregator's dataset-shape bug. Those are
  payload, not process.
- Automating the tag→deploy trigger. Manual dispatch stays; the gap this design
  closes is *visibility*, not automation.
- A migration framework. MongoEngine is schemaless; there are no ordered
  migrations to sequence.

## Constraints that shape the design

- **Hosts carry hand-edits.** The prod tree diverges from `main` by thousands of
  lines and has no `origin` remote; the sidecar has no `.git` at all. The
  process must never `git checkout` on a host. Shipping built images makes the
  host's git state irrelevant, and this property must be preserved.
- **`create_indexes` is idempotent.** `Document.ensure_indexes()` leaves existing
  indexes untouched and drops nothing, so running it on every upgrade is cheap
  when no index changed. It is expensive exactly once — when a release adds an
  index to the 42M-variant collection — and that is when it must run.
- **Recreated containers get new IPs and nginx caches the old ones**, so nginx
  must be reloaded after any recreate or the stack 502s while healthy.
- **`deploy.yml` uses `${{ github.repository }}`** for image paths, so GHCR paths
  follow a repository transfer automatically.

## Design

Four phases in dependency order. Phase 1 is the precondition for 2 and 3.

### Phase 0 — Move to the AfriGen-D org (prerequisite, owner action)

Transfer `mamanambiya/afrigen-beacon-v2` to `AfriGen-D/variant-checker-beacon`,
and the aggregator to `AfriGen-D/variant-checker-beacon-network`.

Rationale: a GA4GH reference implementation that a partner institution has
already adopted should not live in a personal namespace, and the upgrade path
designed below publishes URLs that external operators will bake into their
deployments. Moving after publication invalidates exactly the references we ask
adopters to depend on.

Migration concerns, in order of risk:

1. **GHCR packages may not follow a repository transfer** — unverified; the
   packages API returned 403 (`read:packages` scope missing) so this was not
   established and must be checked before the move. Prod currently runs
   `ghcr.io/mamanambiya/afrigen-beacon-v2/beacon-api:v1.1.4`, and six older tags
   are cached on the host. After the transfer, new pushes go to the org path
   while old tags remain in the personal namespace. Mitigation: keep the old
   package readable, and have the first org-namespace release re-publish the
   current version so a rollback target exists on the new path.
2. **Actions secrets** — all eight (`DEPLOY_*`, `SIDECAR_*`, `JUMPHOST_*`) must
   be confirmed present after transfer, or re-added.
3. **Visibility** — this repo is public, the aggregator is private. Siblings
   should be a deliberate choice; public is an asset for an implementation
   others adopt.

Low risk: git remotes redirect, open PRs and issues transfer, and the
`afrigend-beacon2` strings in the tree are a subdirectory name and a host path,
not the repository name.

### Phase 1 — Release marker (build now, no dependency on Phase 0)

Stamp the release into the image at build time and report it.

- `Dockerfile.boolean` gains `ARG BEACON_RELEASE` → `ENV BEACON_RELEASE`.
- `deploy.yml`'s build step passes the tag being built.
- `/api/health` gains a `release` field beside the existing spec `version`:

```json
{"status": "healthy", "version": "2.0.0-boolean", "release": "v1.1.5", ...}
```

`version` keeps its current meaning (GA4GH spec conformance) and is untouched —
external consumers depend on it. `release` is additive.

When the variable is absent (a local `docker compose build`, a developer's
laptop), `release` reports `"unknown"` rather than being omitted, so a consumer
never has to distinguish "missing field" from "old instance".

### Phase 2 — `scripts/upgrade.sh` (after Phase 0)

One script, two callers. Given a version tag it:

1. Resolves and pulls the pinned API and frontend images.
2. Runs `create_indexes --dry-run` and prints which indexes would be built —
   the preflight that stops a release silently blocking writes on the 42M
   collection.
3. Swaps the images and brings the stack up.
4. Runs `create_indexes`.
5. Reloads nginx.
6. Verifies `/api/health` returns `status: healthy` **and** `release` equal to
   the version requested.
7. On any failure, rolls back to the previously running tag and re-verifies.

`deploy.yml` calls this script over SSH instead of carrying inline deploy logic,
so the maintainers' deploys exercise the same path an external operator runs.
Under a docs-only alternative the external path is only ever exercised by the
external operator — untested by construction.

Step 6 is what makes the upgrade self-verifying: comparing the served marker
against the requested version detects a pull that silently served a cached
image, which a health check alone cannot.

### Phase 3 — Drift check (after Phase 0)

A scheduled workflow that, for each known instance, fetches `/api/health`,
reads `release`, compares against the latest tag, and reports anything behind —
including the case no instance can report: *a tag exists that nothing is
running*.

The instance list is committed to the repo, so adding a beacon to the watch is
a pull request. ARDI is on the list from day one.

Also in this phase: `cleanup` in `deploy.yml` becomes non-gating, so a
successful deploy cannot be reported as a failure.

## Error handling

- **Unreachable instance in the drift check** — reported as `UNKNOWN`, never as
  up-to-date. A transport failure and a current instance must not look alike.
- **429 from an instance** (the live ARDI case) — reported distinctly from
  offline. The beacon answered; it declined to serve. This mirrors the
  aggregator's existing `throttled` handling.
- **`release: "unknown"`** — reported as un-upgradeable-by-this-process rather
  than stale, since it means the image predates Phase 1.
- **Rollback failure in `upgrade.sh`** — exits non-zero, loudly, leaving the
  stack as-is. A rollback that fails silently is worse than one that never ran.

## Testing

- **Phase 1** — assert `/api/health` reports the injected release; assert the
  fallback is `"unknown"` when the build arg is absent. Mutation check: remove
  the `ENV` line and confirm the test fails.
- **Phase 2** — `upgrade.sh` is exercised on every maintainer deploy, which is
  the point of the shared path. Add a dry-run mode for CI that resolves images
  and runs the preflight without swapping.
- **Phase 3** — run the drift check against a known-stale instance (ARDI
  qualifies today) and confirm it reports stale; run against prod after a
  successful upgrade and confirm it reports current. Per the control rule, the
  detector must be shown to fire before its silence is trusted.

## Open questions

1. Whether the eight Actions secrets survive the org transfer, or need re-adding.
2. Whether existing GHCR packages can be made readable from the org namespace,
   or whether the current version must be re-published to give rollback a target.
3. Whether the aggregator repo is renamed in the same change or separately.

## Sequencing

Phase 1 has no dependency on the move and can start immediately. Phases 2 and 3
bake in repository URLs and should wait for Phase 0, so the upgrade path is
published once, under its final identity.
