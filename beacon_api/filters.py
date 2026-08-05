"""
Beacon v2 ``filters`` (ontology-term filtering) request handling.

Standalone by design — no Django, DRF or MongoEngine imports — so it can be
unit-tested without a settings module or a database (see
``beacon_api/test_pagination_filters.py``), matching
``beacon_api/query_semantics.py`` and ``beacon_api/query_sanitizers.py``.

The bug this replaces
---------------------
``BeaconQuerySerializer`` had no ``filters`` field. DRF drops unknown fields,
so a request carrying ``filters`` was answered as though no filter had been
sent — with a 200 and an ``exists`` computed over the *unfiltered* population.
The client believes it asked a narrow question and receives the answer to a
broad one. On a discovery service that silently widens a query, that is a
correctness failure, not a missing feature: a "YES" that means "yes, somewhere
in the whole panel" is indistinguishable from "yes, in the cohort you asked
about".

Why this beacon rejects rather than implements
----------------------------------------------
1. ``/filtering_terms`` is the spec's discovery mechanism for what may appear
   in ``filters``, and it returns an empty list — nothing populates the
   ``FilteringTerm`` collection. This beacon therefore publishes **zero**
   filtering terms, which makes every submitted filter an unresolvable term.
2. The Beacon v2 framework's handling for a term the beacon cannot resolve is
   an error response, not a silently-widened query.
3. Wiring ``filters`` to an ad-hoc mapping over model fields (say, filter id
   -> ``Individual.sex``) would create a filtering vocabulary that is not
   published anywhere a client can discover it. That swaps a silent widening
   for an undiscoverable narrowing — the same dishonesty, one level up.

The rejection is unconditional and does not consult the ``FilteringTerm``
collection: doing so would make the endpoint's contract depend on whether a
data load happened to have run, which is precisely the kind of invisible
behaviour change this module exists to prevent.
"""

# Bound on what is echoed back in an error message. `filters` is
# attacker-controlled on an unauthenticated endpoint, so the terms named in
# the 400 are truncated rather than reflected wholesale.
MAX_ECHOED_FILTERS = 5
MAX_ECHOED_TERM_LENGTH = 64


class UnsupportedFilters(ValueError):
    """The request carries ``filters``, which this beacon cannot honour."""


def normalize_filters(raw):
    """Reduce a ``filters`` value of any accepted shape to a list of term ids.

    The spec permits several shapes, and GET and POST differ:

    * ``filters=NCIT:C16576``                     -> ``['NCIT:C16576']``
    * ``filters=NCIT:C16576,HP:0001250``          -> two ids (GET comma form)
    * ``["NCIT:C16576"]``                         -> one id (POST, id-only)
    * ``[{"id": "NCIT:C16576", "operator": "="}]``-> one id (POST, full form)

    Anything else contributes nothing. An empty or whitespace-only value
    yields ``[]``, i.e. "no filters were sent" — a bare ``?filters=`` must not
    trip the rejection below, since it narrows nothing.
    """
    if raw is None:
        return []

    if isinstance(raw, str):
        candidates = raw.split(',')
    elif isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    elif isinstance(raw, dict):
        # A lone filter object rather than a list of them.
        candidates = [raw]
    else:
        candidates = [raw]

    terms = []
    for item in candidates:
        if isinstance(item, dict):
            item = item.get('id')
        if item is None:
            continue
        if not isinstance(item, str):
            item = str(item)
        item = item.strip()
        if item:
            terms.append(item)
    return terms


def has_filters(params):
    """True if `params` carries at least one non-empty filter term."""
    if not isinstance(params, dict):
        return False
    return bool(normalize_filters(params.get('filters')))


def _describe(terms):
    shown = [t[:MAX_ECHOED_TERM_LENGTH] for t in terms[:MAX_ECHOED_FILTERS]]
    if len(terms) > MAX_ECHOED_FILTERS:
        shown.append('...')
    return ', '.join(shown)


def reject_filters(params):
    """Raise :class:`UnsupportedFilters` if `params` carries any filter term.

    Call this *before* the query is built. Returning the honest error is the
    whole point: the alternative the caller must never fall back to is
    answering the unfiltered question.
    """
    terms = normalize_filters(params.get('filters')) if isinstance(params, dict) else []
    if not terms:
        return
    raise UnsupportedFilters(
        'This beacon does not support the filters parameter. It publishes no '
        'filtering terms (/filtering_terms is empty), so the requested '
        f'term(s) cannot be resolved: {_describe(terms)}. Resubmit without '
        'filters; the response would otherwise cover the whole panel rather '
        'than the subset you asked for.'
    )
