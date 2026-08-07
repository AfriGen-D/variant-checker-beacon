# Deployment prerequisites and post-deploy verification

Everything in `beacon_api/` and `frontend/` ships in the container images, so a
new installation gets the code for free. **What does not ship is host and
database state**, and every outage and silent failure this service has had came
from that gap rather than from the code.

This document is the list of things a new installation must set up, and — more
importantly — **how to prove each one actually works**. A health check does not
prove it. The container reported healthy for months while running months-old
code, while never writing an audit record, and while returning a broken logo.

## The failure mode to design against

The same image behaves differently on two installations today:

| Installation | MongoDB auth | `query_logs` rows |
| --- | --- | --- |
| `afrigend-beacon-network` (sidecar) | none | **165** |
| `afrigend-beacon-prod` | user with `read` role only | **0** |

Neither reports an error. `QueryLogMiddleware` wraps its writes in
`try`/`except` so a logging failure never blocks a beacon response — correct
design, and precisely what hides the problem. **Assume nothing works until you
have queried for the evidence.**

## 1. MongoDB user privileges

The API needs `read` on the genomic collections and `insert` on `query_logs`.
A `read`-only user silently disables the entire audit trail.

Do **not** grant blanket `readWrite` on the database: this is a public,
unauthenticated API and that would let it modify the variant data. Use the
collection-scoped role in `scripts/grant_query_log_writer.js`.

**Verify — do not assume:**

```bash
docker exec <api-container> python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'beacon_project.settings_boolean')
django.setup()
from mongoengine.connection import get_db; db=get_db()
print(db.command('connectionStatus')['authInfo']['authenticatedUserRoles'])
print('query_logs:', db.query_logs.estimated_document_count())
"
```

Issue a query against `/api/g_variants`, run it again, and confirm the count
increased. If it does not, the audit trail is not recording, whatever the code
says.

## 2. Indexes

Locus queries rely on a compound index on `{reference_name, start}`. Check what
exists before assuming anything is missing — on the production node this index
already existed while the timeouts were being blamed on its absence:

```bash
docker exec <api-container> python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'beacon_project.settings_boolean')
django.setup()
from mongoengine.connection import get_db
for n, s in get_db().variants.index_information().items(): print(n, s.get('key'))
"
```

`manage.py create_indexes` adds the rest. It needs `createIndex`, which the
read-only user does not have. Index builds on MongoDB 4.2+ are **not**
write-blocking — `background` is deprecated and ignored, and the build yields to
reads and writes except for brief locks at start and end.

## 3. Reverse proxy after any container recreate

nginx resolves upstream container names **once at startup**. A recreated
container gets a new IP, so the stack returns 502 even though the API is
healthy. Always follow a recreate with:

```bash
docker exec <nginx-container> nginx -s reload
```

The deploy pipeline does this automatically. Manual `docker compose up` does
not.

## 4. Settings worth reviewing per installation

All have working defaults; these are the ones whose *correct* value depends on
the data:

**`BEACON_MAX_VARIANT_SPAN`** (default 10000)
Review when **structural variants are loaded**. A variant longer than this
that overlaps the queried position from below will not be found.

**`BEACON_QUERY_MAX_TIME_MS`** (default 5000)
Review when queries legitimately exceed it — but first check the query is
index-bounded, rather than raising this.

**`BEACON_AF_MIN_PUBLISHED`** / **`BEACON_AF_DECIMALS`** (0.01 / 3)
Review when cohort size differs. The defaults are sized for ~1,895 samples;
a smaller cohort needs coarser publishing to avoid disclosing carrier counts.

**`BEACON_QUERYLOG_RETENTION_DAYS`** (default 90)
Review when local data-governance rules differ.

## 5. Static assets

`frontend/public/*.png` must be committed. A blanket `*.png` ignore rule once
excluded the site logo, which went unnoticed while images were built on the host
from a tree that happened to contain it — and 404'd the moment CI began building
from a clean checkout. **Anything the host has that git does not will vanish as
soon as builds become reproducible.**

## 6. Post-deploy verification

Health endpoints prove almost nothing. Run these against the deployed URL:

```bash
B=https://<host>/api

# Answers, not just liveness — an unparameterized query must return fast
curl -s -o /dev/null -w "all-entries %{http_code} %{time_total}s\n" "$B/g_variants"

# A locus at a HIGH coordinate. Low coordinates can pass while high ones
# time out, because query cost grows with position if the filter is unbounded.
curl -s -o /dev/null -w "high locus  %{http_code} %{time_total}s\n" \
  "$B/g_variants?assemblyId=GRCh38&referenceName=2&start=178545626"

# Spec conformance (17 checks)
docker run --rm beacon-verifier:latest "$B/"
```

Then confirm the deployed code is the code you think it is. `docker compose ps`
showing "healthy" does not tell you the image is current:

```bash
docker exec <api-container> python -c "import beacon_api.query_cost" && echo present
```

Verify with a probe for something the release actually introduced, and use word
boundaries — `grep -c "start__lt"` also matches `start__lte`, the very pattern it
is meant to distinguish.
