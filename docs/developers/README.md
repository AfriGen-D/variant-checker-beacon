# Developer documentation

Start here if you are going to change this codebase.

This folder is deliberately short. The repository already carries about 13,000
lines of documentation, and a 2026-08-13 audit found substantial drift in it —
including client examples that do not work. These pages cover what a developer
needs to be productive and safe, and tell you which of the older documents to
trust.

Every command on these pages was run against the repository on 2026-08-19. Where
something is unverified, it says so.

## The pages

| Page | Read it when |
| ------ | -------------- |
| [getting-started.md](getting-started.md) | First day. Getting the stack running locally. |
| [architecture.md](architecture.md) | Before changing query behaviour. How a query becomes an answer. |
| [testing.md](testing.md) | Before opening any PR. What runs, what gates a merge. |
| [api-contract.md](api-contract.md) | Writing a client, or changing a response shape. |
| [contributing.md](contributing.md) | Branching, commits, PRs, and what you may not do. |

## The one thing to internalise first

**A wrong "no" is this project's worst failure mode.**

This is a discovery beacon. It answers "do you hold this variant?" A false
negative — answering `exists: false` for a variant the panel actually holds — is
indistinguishable from a true negative to every caller. Nobody files a bug,
because nothing looks broken. A researcher simply concludes the variant is not in
African reference data and moves on.

Three consequences for how you work here:

1. **Never silently drop a query parameter.** If the beacon cannot apply a filter,
   it must refuse the query, not answer a broader one. `beacon_api/filters.py`
   is the reference implementation of this judgement and its docstring explains
   the reasoning.
2. **A green GA4GH verifier run proves nothing about answers.** `beacon-verifier`
   checks envelope shape. It passed 17/17 for the entire period during which
   position queries were off by one base and multi-allelic sites were
   unqueryable.
3. **Coordinate and vocabulary handling is where the bugs live.** Half-open vs
   closed intervals, 0-based vs 1-based, `chr1` vs `1`, `hg38` vs `GRCh38`. Each
   has caused a real false negative in this codebase.

## Which existing documents to trust

The audit assessed the older documentation. Summary, so you do not have to
rediscover it:

| Document | Status |
| ---------- | -------- |
| `docs/DEPLOYMENT_PREREQUISITES.md` | **Trust.** The most accurate operational document in the repo. Explains why health endpoints prove almost nothing. Nothing links to it, which is why you have not read it. |
| `CLAUDE.md` | **Mostly trust.** Unusually honest — it flags scripts that earlier revisions invented and marks `scripts/deploy.sh` do-not-run. Its CI/CD section and its claim that the API sidecar is down are stale. |
| `docs/SPEC_CONFORMANCE.md` | **Trust the caveat, not the score.** It correctly warns that a green verifier says nothing about query semantics. The evidence file it cites is not in the repo. |
| `docs/API_REFERENCE.md` | **Partially.** The endpoint list is useful; the client examples parse a field the API does not return. See [api-contract.md](api-contract.md). |
| `docs/BOOLEAN_MODE.md` | **Careful.** Same broken `.exists` examples, and it advertises GA4GH AAI with a four-step upgrade guide whose first step cannot succeed — that capability does not exist. |
| `docs/TESTING.md` | **Careful.** Six months old and predates the current suites. Use [testing.md](testing.md). |
| `CONTRIBUTING.md` | **Careful.** Six months old. Code of conduct and PR etiquette still apply; the commands have drifted. Use [contributing.md](contributing.md). |
| `docs/PROJECT_OVERVIEW.md` | **Careful.** 3,081 lines, and it documents a `scripts/backup.sh` that does not exist. |

## Known-wrong things you will otherwise trip over

These are confirmed, not suspected. Each is either fixed in an open PR or still
open; none is a mystery.

- Documented client examples parse `.exists` at the **top level**. The API has
  never returned that. It is `responseSummary.exists`.
- `npm run test:ci` in `frontend/` runs Jest against **zero test files**. Jest is
  declared as a dependency; no test file exists.
- `scripts/deploy.sh` targets a compose file production does not use, with
  different volume names. Running it would start a second, empty MongoDB
  alongside the live one.
- `scripts/monitor_beacon.sh` checks a container name that does not exist in
  production, so it is permanently red and alerts on nothing.
- `beacon_api/test_middleware.py` needs Django, and Django 4.0 cannot import on
  Python 3.13+ (it needs the removed `cgi` module). Use Python 3.9–3.12 for
  anything that imports Django.

## Getting help

- Architecture and query semantics: read the module docstrings first. Several
  carry real post-mortems — `query_cost.py` records the 30.7-second production
  incident that motivated the query budget.
- Operational questions: `docs/DEPLOYMENT_PREREQUISITES.md`, then `CLAUDE.md`.
- The full audit, including a ranked work sequence, is linked from the
  repository's issue tracker.
