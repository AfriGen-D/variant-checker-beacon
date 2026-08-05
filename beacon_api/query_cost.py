"""
Classification of a built variant query by how much work it can cost.

Standalone by design — no Django, DRF, MongoEngine or pymongo imports — so the
classification can be unit-tested without a settings module or a database (see
``beacon_api/test_pagination_filters.py``), matching
``beacon_api/query_semantics.py`` and ``beacon_api/query_sanitizers.py``.

The bug this exists to prevent
------------------------------
``GET /api/g_variants`` with no parameters at all timed out in production
(HTTP 504 after 30.7s) and was the single failing check in the GA4GH
``beacon-verifier`` run ("Genomic Variants all entries": ``operation timed
out``). The guard it slipped past was::

    if any(k in mongo_query for k in POSITION_FILTER_KEYS) and \\
            'reference_name__in' not in mongo_query:
        return 400

That fires only when a *position* is present. A parameterless request builds no
position key, so it skipped the guard entirely.

The expensive part is not the existence probe — ``.first()`` on a broad filter
returns as soon as any document matches. It is the **per-dataset attribution
loop**, which re-queries ``base_qs.filter(dataset_ids=<id>)`` once per dataset.
``dataset_ids`` is frequently unset on stored variants, so a probe that matches
nothing walks the whole ~42M-document collection before it can report "no". One
unauthenticated request therefore occupies a gunicorn worker for 30s+, and with
``--workers 4`` four concurrent requests saturate the API. That is a denial-of-
service vector, not merely a slow endpoint.

Why not just reject the parameterless request
---------------------------------------------
Beacon v2 defines a parameterless ``/g_variants`` as the legitimate "all
entries" request, and the verifier issues exactly that and expects a valid
response. Answering 400 would trade a timeout for a conformance failure. The
correct answer is a bounded, quick, spec-shaped response.
"""

# Keys build_position_filter() emits, duplicated from query_semantics only as a
# fallback default; callers pass the real constant in so the two cannot drift.
_DEFAULT_POSITION_KEYS = ('start__lt', 'end__gt')

# Filter keys that narrow the match to something an index can serve cheaply.
# `assembly_id` is deliberately absent: it is applied to every query (the
# serializer defaults assemblyId to GRCh38), so its presence carries no
# selectivity at all — treating it as a constraint is precisely how a
# parameterless request looked "filtered" and escaped the old guard.
SELECTIVE_KEYS = ('reference_name__in', 'reference_bases', 'alternate_bases')

# A query that can use the {reference_name, start, end} compound index.
QUERY_LOCUS = 'locus'

# Some constraint, but not one that bounds the candidate set to a locus — e.g.
# referenceName with no position, which is a full-chromosome scan.
QUERY_PARTIAL = 'partial'

# No selective constraint whatsoever: the Beacon v2 "all entries" request.
QUERY_UNBOUNDED = 'unbounded'

# Server-side time budget for any variant-collection query, in milliseconds.
# This is the only bound that holds in the worst case: `limit` does NOT bound a
# query that matches nothing, because MongoDB still scans the entire collection
# looking for documents to fill the page.
DEFAULT_QUERY_MAX_TIME_MS = 5000


def classify_variant_query(mongo_query, position_keys=_DEFAULT_POSITION_KEYS):
    """Classify a built MongoEngine filter dict as locus/partial/unbounded.

    Returns one of :data:`QUERY_LOCUS`, :data:`QUERY_PARTIAL`,
    :data:`QUERY_UNBOUNDED`.
    """
    has_position = any(k in mongo_query for k in position_keys)
    has_chromosome = 'reference_name__in' in mongo_query

    if has_chromosome and has_position:
        return QUERY_LOCUS
    if any(k in mongo_query for k in SELECTIVE_KEYS) or has_position:
        return QUERY_PARTIAL
    return QUERY_UNBOUNDED


def allows_per_dataset_attribution(query_class):
    """True if the per-dataset attribution loop is safe to run.

    Only a locus query bounds the candidate set tightly enough that N extra
    ``dataset_ids`` probes are cheap. For anything broader each probe is a
    potential collection scan, which is the DoS above.
    """
    return query_class == QUERY_LOCUS
