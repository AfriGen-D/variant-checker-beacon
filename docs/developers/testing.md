# Testing

What exists, what runs, and what gates a merge.

## The suites that matter

Four backend suites are **Django-free by design** — no settings module, no
database, no network — so they run on a bare interpreter in milliseconds:

```bash
python3 -m unittest \
  beacon_api.test_query_semantics \
  beacon_api.test_query_injection \
  beacon_api.test_pagination_filters \
  beacon_api.test_assembly
```

```text
Ran 144 tests in 0.001s

OK
```

| Suite | Tests | Covers |
| --- | --- | --- |
| `test_query_semantics` | 24 | Half-open coordinate overlap, span bounds |
| `test_query_injection` | 53 | NoSQL operator injection, AF privacy, IP anonymisation |
| `test_pagination_filters` | 50 | Skip/limit, filter rejection |
| `test_assembly` | 17 | Assembly canonicalisation |
| `test_query_vocabulary` | 26 | variantType / datasetIds / sex — apply or refuse |
| `test_capabilities` | 15 | Unimplemented endpoints answer 501, never "no" |
| `test_release` | 6 | The release marker on `/api/health` |
| `test_request_body` | 9 | Spec-shaped POST bodies reach the query |

`test_middleware` is the exception — it imports Django, so it needs Python 3.9
to 3.12. Django 4.0 imports `cgi`, removed in Python 3.13.

## What gates a merge

All four suites, as of 2026-08-19. The `test` job in `ci-cd.yml` runs them
before installing anything, so a query-correctness regression fails a PR in
seconds. It costs about 5 milliseconds.

That gate is new. Until it landed, **none** of these ran on a pull request:
`ci-cd.yml` ran pytest scoped to `afrigend-beacon2-tools`, and the single
backend module that did run (`test_middleware`) ran in `deploy.yml` at deploy
time — after the merge it should have blocked. If you add a suite, add it to
that step in the same PR, or it sits in the repository ungated.

The frontend gates are `npm run type-check` and `npm run lint`. **`npm run
test:ci` runs Jest against zero test files** — Jest is a declared dependency and
no test file exists. A pass there means nothing.

## Data tools

```bash
cd afrigend-beacon2-tools
pytest tests/ -m "not requires_cyvcf2" --ignore=tests/integration/test_vcf_pipeline.py
```

Gated at 80% coverage by `pyproject.toml`. Tests needing `cyvcf2`, `pybedtools`
or `pysam` are skipped because those need native system libraries.

## How to write a test here

Two rules, both learned from real incidents in this repository.

**Watch it fail first, for the right reason.** A test written after the code
passes immediately, which proves nothing — it may test the implementation you
just wrote rather than the behaviour you wanted. If a test errors on an import
or a fixture, that is not a red; repair it and re-run until it fails on the
assertion.

**Mutation-check any guard you add.** Temporarily invert or remove the thing the
test protects, confirm the suite goes red, then restore. Several guards in this
repo's history passed their own tests while those tests could not have caught
their removal.

`test_query_semantics.py` is the model to copy. It contains a `LegacyContrast`
suite written specifically so that reverting to the old closed-interval
comparison goes red, and it pins a *known limitation* under the name
`test_span_bound_misses_a_variant_longer_than_the_span` with the comment
"pinned so it cannot change unnoticed".

## Keep new logic Django-free where you can

If the logic is pure — coordinates, vocabulary, filter shapes — put it in its
own module with no Django import and test it standalone. `query_semantics.py`
and `assembly.py` follow this. It is why the merge gate costs milliseconds
rather than a CI job with a database.

## What a green run does not tell you

The GA4GH `beacon-verifier` checks envelope shape only. It passed 17/17
throughout the period when position queries were off by one base and
multi-allelic sites were unqueryable. **A green verifier run is not evidence
that the beacon returns correct answers.** Neither is a passing health check —
it proves the API can reach MongoDB and Redis, nothing more.

For query correctness the only real check is asking the beacon a question whose
answer you independently know, including a negative control. The tutorial does
exactly this in Steps 7 and 8.
