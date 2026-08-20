# Release Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every beacon instance report which release of the code it is running, over plain HTTP, so drift can be measured instead of discovered by accident.

**Architecture:** A Django-free module reads a `BEACON_RELEASE` environment variable that the Dockerfile stamps at build time from the git tag, and the boolean-mode health endpoint reports it as a new `release` field. The existing `version` field is left untouched. Keeping the logic in its own module means the change to `views_boolean.py` is a single line, which matters because that file has concurrent work in PR #48.

**Tech Stack:** Python 3.9, Django 4.0.10, DRF, Docker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-19-beacon-release-and-upgrade-design.md`

## Global Constraints

- **Do not change the existing `version` field.** It reports
  `settings.BEACON_API_VERSION` and external consumers depend on it. `release`
  is strictly additive.
- **`release` is always present.** When the variable is absent it reports the
  string `unknown`, never an omitted key, so a consumer never has to
  distinguish "old instance" from "missing field".
- **Python 3.9** — no `match`, no `str.removeprefix` in library code paths that
  must run on the image.
- **New tests must be Django-free where possible** and registered in the
  `Run backend query-correctness tests` step of `.github/workflows/ci-cd.yml`,
  which runs `python -m unittest` against an explicit module list.
- **Do not edit `.github/workflows/ci-cd.yml` until PR #48 has landed.** That
  step has been modified by #44, #47 and #48. Rebase first or expect a
  conflict.

## File Structure

| File | Responsibility |
| --- | --- |
| `beacon_api/release.py` (create) | Read and normalise the build-time release stamp. No Django, no DRF, no MongoEngine. |
| `beacon_api/test_release.py` (create) | Plain-unittest coverage for the above. |
| `beacon_api/views_boolean.py` (modify) | One import, one dict key in `health_check`. |
| `Dockerfile.boolean` (modify) | Declare `ARG BEACON_RELEASE` and promote it to `ENV`, placed late so it does not bust the dependency cache layer. |
| `.github/workflows/deploy.yml` (modify) | Pass the tag being built as a build-arg to the API image. |
| `.github/workflows/ci-cd.yml` (modify) | Register `beacon_api.test_release` in the unittest module list. |

---

### Task 1: The release module

**Files:**

- Create: `beacon_api/release.py`
- Test: `beacon_api/test_release.py`
- Modify: `.github/workflows/ci-cd.yml` (unittest module list)

**Interfaces:**

- Consumes: nothing.
- Produces: `beacon_api.release.get_release(environ=None) -> str` and the
  constant `UNKNOWN_RELEASE = 'unknown'`. Task 2 imports `get_release`.

- [ ] **Step 1: Write the failing test**

Create `beacon_api/test_release.py`:

```python
"""
Tests for the build-time release stamp.

Standalone: ``beacon_api.release`` imports no Django, DRF or MongoEngine, so
these run with plain unittest and need no settings module, database or network.

    python3 -m unittest beacon_api.test_release -v
"""
import unittest

from beacon_api.release import UNKNOWN_RELEASE, get_release


class GetReleaseTests(unittest.TestCase):
    def test_reports_the_stamped_release(self):
        self.assertEqual(get_release({'BEACON_RELEASE': 'v1.1.5'}), 'v1.1.5')

    def test_unset_reports_unknown(self):
        self.assertEqual(get_release({}), UNKNOWN_RELEASE)

    def test_empty_reports_unknown(self):
        # `ARG BEACON_RELEASE=""` that is declared but never passed expands to
        # the empty string, not to an unset variable.
        self.assertEqual(get_release({'BEACON_RELEASE': ''}), UNKNOWN_RELEASE)

    def test_whitespace_only_reports_unknown(self):
        self.assertEqual(get_release({'BEACON_RELEASE': '  \n'}), UNKNOWN_RELEASE)

    def test_strips_surrounding_whitespace(self):
        # A YAML block-scalar build-arg carries a trailing newline into the
        # environment; reporting 'v1.1.5\n' would fail an equality check
        # against the requested version in the upgrade script.
        self.assertEqual(get_release({'BEACON_RELEASE': ' v1.1.5\n'}), 'v1.1.5')

    def test_unknown_is_the_literal_string_unknown(self):
        # The drift check distinguishes "stale" from "predates the marker" by
        # this exact value; renaming it silently breaks that branch.
        self.assertEqual(UNKNOWN_RELEASE, 'unknown')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd <repo root> && python3 -m unittest beacon_api.test_release -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'beacon_api.release'`.

If it fails for any other reason, stop and fix that first: a test that errored
on an import is not a red for the behaviour under test.

- [ ] **Step 3: Write the minimal implementation**

Create `beacon_api/release.py`:

```python
"""
The release of the beacon code that this container is running.

Deliberately free of Django, DRF and MongoEngine so it can be unit-tested with
plain unittest, and imported from anywhere without pulling in settings.

Why this is not ``settings.BEACON_API_VERSION``: that value is
``config('BEACON_API_VERSION', default='v2.0.0')``
(``beacon_project/settings_boolean.py:226``) — it describes the GA4GH spec
level, it is operator-settable, and it is a constant across releases. On
2026-08-19 production and a deployment three and a half months behind it
returned the identical string from ``/api/health``, which is precisely why
three instances drifted with nothing reporting it.
"""
import os

UNKNOWN_RELEASE = 'unknown'


def get_release(environ=None):
    """
    Return the release tag stamped into the image at build time.

    ``environ`` is injectable for tests; production passes nothing and reads
    ``os.environ``. Returns ``UNKNOWN_RELEASE`` when the stamp is missing or
    blank, never an empty string — a consumer should not have to tell an
    unstamped image apart from a missing field.
    """
    env = os.environ if environ is None else environ
    return (env.get('BEACON_RELEASE') or '').strip() or UNKNOWN_RELEASE
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest beacon_api.test_release -v`

Expected: PASS, 6 tests.

- [ ] **Step 5: Mutation-check the test**

Temporarily change the `.strip()` to nothing in `get_release`, re-run, and
confirm `test_strips_surrounding_whitespace` FAILS. Then restore it and
re-run to confirm PASS. A guard whose test cannot fail when the guard is
removed is not covered.

- [ ] **Step 6: Register the test in CI**

Only after PR #48 has landed — see Global Constraints. In
`.github/workflows/ci-cd.yml`, add `beacon_api.test_release` to the module
list in the `Run backend query-correctness tests` step:

```yaml
          python -m unittest \
            beacon_api.test_query_semantics \
            beacon_api.test_query_injection \
            beacon_api.test_pagination_filters \
            beacon_api.test_assembly \
            beacon_api.test_release
```

- [ ] **Step 7: Commit**

```bash
git add beacon_api/release.py beacon_api/test_release.py .github/workflows/ci-cd.yml
git commit -m "feat(release): report which code a beacon instance is running"
```

---

### Task 2: Report the release on /api/health, and stamp it at build

**Files:**

- Modify: `beacon_api/views_boolean.py` (import near the top; `health_check` return at ~line 812-820)
- Modify: `Dockerfile.boolean`

**Interfaces:**

- Consumes: `beacon_api.release.get_release` from Task 1.
- Produces: `GET /api/health` responds with a `release` key alongside `version`.
  Task 3 and the Phase 2 upgrade script compare that value against the
  requested tag.

- [ ] **Step 1: Add the import to `beacon_api/views_boolean.py`**

Beside the other first-party imports (the file already does
`from .models import Dataset` inside `health_check`; put this one at module
level with the other `from .` imports):

```python
from .release import get_release
```

- [ ] **Step 2: Add the field to the health response**

In `health_check`, the return is currently:

```python
    return Response({
        'status': overall,
        'version': settings.BEACON_API_VERSION,
        'services': {
            'database': db_status,
            'cache': cache_status,
        },
        'timestamp': datetime.now().isoformat()
    }, status=status_code)
```

Add exactly one key — leave `version` alone:

```python
    return Response({
        'status': overall,
        'version': settings.BEACON_API_VERSION,
        'release': get_release(),
        'services': {
            'database': db_status,
            'cache': cache_status,
        },
        'timestamp': datetime.now().isoformat()
    }, status=status_code)
```

- [ ] **Step 3: Stamp the release in `Dockerfile.boolean`**

Add these two lines **after** the `COPY` steps and **before** `USER beacon`
(i.e. after line 34, `RUN mkdir -p logs staticfiles ...`). Placement matters:
an `ARG` declared near the top would sit above the `pip install` layer, so
every release change would invalidate the dependency cache and force a full
reinstall on every build.

```dockerfile
# Stamped by CI from the git tag being built; see beacon_api/release.py.
# Declared late on purpose — above the pip layer it would bust the dependency
# cache on every release.
ARG BEACON_RELEASE=""
ENV BEACON_RELEASE=${BEACON_RELEASE}
```

- [ ] **Step 4: Build the image locally and verify the stamp reaches the container**

```bash
docker build -f Dockerfile.boolean --build-arg BEACON_RELEASE=v9.9.9-test -t beacon-release-test .
docker run --rm beacon-release-test python -c "from beacon_api.release import get_release; print(get_release())"
```

Expected output: `v9.9.9-test`

- [ ] **Step 5: Verify the unstamped case reports `unknown`**

This is the control — the check must be shown to distinguish the two states,
not merely to pass once.

```bash
docker build -f Dockerfile.boolean -t beacon-release-test-bare .
docker run --rm beacon-release-test-bare python -c "from beacon_api.release import get_release; print(get_release())"
```

Expected output: `unknown`

- [ ] **Step 6: Verify the live endpoint reports it**

Bring up the dev stack and read the endpoint, so the assertion is against the
served response rather than the module:

```bash
docker compose -f compose/docker-compose.dev.yml up -d --build
curl -s http://localhost:8000/api/health
```

Expected: the JSON contains both `"version"` and `"release"`. In the dev stack
no build-arg is passed, so `"release":"unknown"` is the correct result here.

```bash
docker compose -f compose/docker-compose.dev.yml down
```

- [ ] **Step 7: Commit**

```bash
git add beacon_api/views_boolean.py Dockerfile.boolean
git commit -m "feat(health): report the build-stamped release alongside the spec version"
```

---

### Task 3: Pass the tag at build time in the deploy pipeline

**Files:**

- Modify: `.github/workflows/deploy.yml` (the `Build and push API image` step, ~line 151-162)

**Interfaces:**

- Consumes: `needs.preflight.outputs.version` (already used for the image tags
  in the same step) and the `ARG BEACON_RELEASE` from Task 2.
- Produces: images whose `/api/health` reports the tag they were built from.

- [ ] **Step 1: Add the build-arg to the API build step**

The step currently has no `build-args`. Add one, mirroring the frontend step
which already uses the same key:

```yaml
      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.boolean
          push: true
          tags: |
            ${{ env.API_IMAGE }}:${{ needs.preflight.outputs.version }}
            ${{ env.API_IMAGE }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            BEACON_RELEASE=${{ needs.preflight.outputs.version }}
```

- [ ] **Step 2: Verify the workflow still parses**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('deploy.yml parses')"
```

Expected: `deploy.yml parses`

- [ ] **Step 3: Confirm the value is the tag, not the branch**

Read the `preflight` job and confirm `outputs.version` is the validated tag
(the job already has a `Validate tag format` and a `Confirm the tag exists`
step). Record in the PR body which line defines it. This is the one value the
whole design rests on; an inherited branch name here would stamp every image
with the same string and silently reproduce the bug being fixed.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: stamp the release tag into the API image at build time"
```

---

## Verification after deploy

Not a task — this is the acceptance check for Phase 1, and it can only run
once a release built by the updated pipeline has shipped.

```bash
curl -s https://beacon.afrigen-d.org/api/health
curl -s https://api-beacon.afrigen-d.dev/api/health
curl -s https://beacon.ardi.africa/api/health
```

Expected once each has been upgraded: `release` equals the tag deployed there.
Until then, an instance reporting `"release":"unknown"` is correctly telling
you it predates this change — which is itself the first true drift signal the
estate has ever produced.

## Out of scope for this plan

Phase 2 (`scripts/upgrade.sh`) and Phase 3 (the scheduled drift check) depend
on the org move and are not started here. Making `cleanup` non-gating in
`deploy.yml` is Phase 3.
