"""
Beacon v2 ``skip``/``limit`` pagination.

Standalone by design — no Django, DRF or MongoEngine imports — so the bounds
below can be unit-tested without a settings module or a database (see
``beacon_api/test_pagination_filters.py``), matching
``beacon_api/query_semantics.py`` and ``beacon_api/query_sanitizers.py``.

Why this exists
---------------
``BeaconQuerySerializer`` had no ``skip``/``limit`` fields, so the spec's
pagination parameters were dropped on the floor — while
``build_received_request_summary`` unconditionally echoed
``{'skip': 0, 'limit': 10}``. The beacon therefore *told* every client it had
applied a page it had never applied. A client paging with ``skip`` got page 1
again, forever, with a response that claimed otherwise.

Bounds
------
Every endpoint here is unauthenticated and sits in front of a ~42M-document
collection, so both parameters are attacker-controlled and must be capped:

* ``limit`` bounds the response body and the documents materialised per
  request.
* ``skip`` bounds server work: MongoDB's ``skip`` walks and discards N
  documents, so an uncapped ``skip=50000000`` is a free collection scan.

Deliberate deviation from the spec default
------------------------------------------
Beacon v2 specifies a default ``limit`` of 10. Applying that default here
would silently truncate ``/datasets``, ``/cohorts`` and ``/filtering_terms``
for every existing caller that omits the parameter — the frontend among them.
So an omitted ``limit`` means "no client-requested page", and the effective
limit becomes :data:`MAX_LIMIT`. The echoed ``receivedRequestSummary`` reports
the limit that was *actually applied*, which is the property that was broken
and is the one worth preserving.
"""

# Largest page a client may request. Metadata collections served here
# (datasets, cohorts, filtering terms) are far smaller than this; the cap
# exists to bound an unauthenticated response body, not to shape normal use.
MAX_LIMIT = 1000

# Largest offset a client may request. MongoDB's skip is O(skip) — it walks
# and throws away every skipped document — so this is a CPU bound, not a
# usability one.
MAX_SKIP = 10_000

# Applied when the caller omits `limit`. See the module docstring: this is
# MAX_LIMIT rather than the spec's 10 so that omitting the parameter keeps the
# pre-pagination behaviour of returning the whole (small) collection.
DEFAULT_LIMIT = MAX_LIMIT

DEFAULT_SKIP = 0


class InvalidPagination(ValueError):
    """A supplied ``skip``/``limit`` cannot be honoured."""


def _coerce_int(value, field_name):
    """Parse `value` as a non-negative integer, or raise InvalidPagination.

    Values arrive either as query-string text (``'25'``) or, on POST, as
    arbitrary JSON — so ``{'$gt': 0}`` and ``[1]`` both have to be refused
    here rather than reaching ``int()`` and 500-ing, and ``True`` must not
    quietly become ``1``.
    """
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        raise InvalidPagination(f'{field_name} must be an integer')

    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        # 10.0 is fine; 10.5 is a client bug worth reporting rather than
        # silently truncating to a different page than was asked for.
        if value != int(value):
            raise InvalidPagination(f'{field_name} must be an integer')
        number = int(value)
    elif isinstance(value, str):
        text = value.strip()
        # int() accepts '  +7 ' and '1_000'; neither is a shape a client should
        # be taught to rely on, and the underscore form makes the echoed value
        # differ from the sent one.
        if not text.lstrip('-').isdigit():
            raise InvalidPagination(f'{field_name} must be an integer')
        number = int(text)
    else:
        raise InvalidPagination(f'{field_name} must be an integer')

    # Checked here rather than only on the string path. A JSON body carries
    # real ints, so `{"skip": -1}` used to sail through — and a negative offset
    # reaches MongoDB's .skip(), which rejects it, turning a client typo into a
    # 500. `{"limit": -5}` was worse: it fell through to clamp_limit() and was
    # silently read as "no preference", quietly serving a different page than
    # the one requested.
    if number < 0:
        raise InvalidPagination(f'{field_name} must be a non-negative integer')
    return number


def clamp_limit(value):
    """Bound a caller-supplied `limit` to ``[1, MAX_LIMIT]``.

    ``limit=0`` means "unlimited" in the Beacon v2 spec. On a public beacon in
    front of tens of millions of documents, honouring that literally is a
    denial-of-service switch, so it is read as "no preference" and mapped to
    the maximum page instead of to infinity.
    """
    if value is None:
        return DEFAULT_LIMIT
    if value <= 0:
        return DEFAULT_LIMIT
    return min(value, MAX_LIMIT)


def parse_pagination(params):
    """Extract ``(skip, limit)`` from a request parameter mapping.

    `params` may be a Django ``QueryDict.dict()`` or a decoded JSON body, so
    every value is untrusted and of unknown type. Absent parameters yield the
    defaults; present-but-unusable ones raise :class:`InvalidPagination` so the
    view can answer 400 rather than pretend the page was applied.

    Returns the *effective* skip and limit — the numbers the caller should
    apply to the queryset AND echo back in ``receivedRequestSummary``.
    """
    if not isinstance(params, dict):
        return DEFAULT_SKIP, DEFAULT_LIMIT

    skip = DEFAULT_SKIP
    if params.get('skip') is not None:
        skip = _coerce_int(params['skip'], 'skip')
        if skip > MAX_SKIP:
            raise InvalidPagination(
                f'skip is too large (max {MAX_SKIP})'
            )

    limit = None
    if params.get('limit') is not None:
        limit = _coerce_int(params['limit'], 'limit')

    return skip, clamp_limit(limit)


def paginate(items, skip, limit):
    """Slice an already-materialised list.

    Used only where the full collection is already in memory and small. Prefer
    pushing ``skip``/``limit`` into the queryset (``.skip().limit()``) whenever
    the collection could be large — slicing after the fact still pays to fetch
    everything, which is exactly the cost the cap is meant to avoid.
    """
    if skip < 0:
        skip = 0
    return list(items)[skip:skip + limit]
