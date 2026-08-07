"""
Genomic coordinate query semantics.

Deliberately free of Django / DRF / MongoEngine imports so the interval logic
can be unit-tested standalone (see ``beacon_api/test_query_semantics.py``)
without a settings module or a live MongoDB.

Coordinate convention
---------------------
Variants are stored in Beacon v2 **0-based half-open** coordinates, as
produced by the VCF transform:

    start = POS - 1
    end   = POS - 1 + len(REF)

so a stored variant occupies the half-open interval ``[start, end)``.

Two half-open intervals ``[a, b)`` and ``[c, d)`` overlap iff::

    a < d  AND  b > c

which in MongoDB terms is ``start__lt = query_end`` and
``end__gt = query_start``. Using ``lte``/``gte`` instead (closed-interval
overlap) makes a variant stored as ``[P-1, P)`` match a query at position
``P`` — i.e. the beacon answers YES for the base immediately *after* the real
variant, and YES at position ``P`` for a variant that actually sits at
``P-1``. That was the bug this module exists to prevent regressing.
"""

# MongoDB query keys emitted by build_position_filter(). Exposed so callers
# can test for "did this query get a position filter?" without hardcoding the
# operator names in two places (they were previously duplicated, and the
# duplicate went stale when the operators changed).
# Fallback when settings does not define BEACON_MAX_VARIANT_SPAN, so the
# module keeps working standalone (and in the secure-mode settings, which
# do not define it).
DEFAULT_MAX_VARIANT_SPAN = 10000

POSITION_FILTER_KEYS = ('start__lt', 'end__gt', 'start__gte')


def build_position_filter(start, end=None, max_variant_span=None):
    """
    Build the MongoDB filter for a Beacon positional query.

    ``start`` (and ``end``) are 0-based Beacon coordinates.

    Two shapes are supported:

    * **Point query** — only ``start`` supplied. This is the standard Beacon v2
      SNV lookup and asks about the *single base* at ``start``, i.e. the
      half-open interval ``[start, start + 1)``. It is emphatically NOT the
      degenerate empty interval ``[start, start)``, which would match nothing.
    * **Range query** — ``start`` and ``end`` supplied: the interval
      ``[start, end)``, with ``end`` exclusive.

    A caller-supplied ``end`` that is not strictly greater than ``start`` is
    treated as a point query. ``BeaconQuerySerializer`` permits ``start == end``
    (``validate_range`` only rejects ``start > end``), and taking that
    literally would yield an empty interval that can never match — a silent
    always-NO. Collapsing it to the single base at ``start`` preserves the
    intent of the query.

    ``max_variant_span`` bounds how far *before* ``start`` a stored variant may
    begin and still be considered. Supplying it makes the query use the
    ``{reference_name, start}`` index as a narrow range instead of scanning
    every variant from the start of the chromosome, which is the difference
    between milliseconds and seconds on a 42M-variant collection.

    It is a correctness/performance trade-off and is therefore explicit: any
    variant longer than ``max_variant_span`` that overlaps ``start`` from below
    will be missed. Omit it (the default) to keep the query exhaustive.

    Returns a dict of MongoEngine filter kwargs.
    """
    if start is None:
        return {}

    query_end = end if (end is not None and end > start) else start + 1

    filters = {
        # variant.start < query_end
        'start__lt': query_end,
        # variant.end > query_start
        'end__gt': start,
    }

    # `start__lt` alone is unbounded below, and that is a performance cliff
    # rather than a correctness problem: the {reference_name, start} index is
    # walked from the first variant on the chromosome up to query_end, so cost
    # grows with the genomic coordinate. Measured on the 42M-variant production
    # panel, a lookup at chr2:178,545,627 took 3.6s warm (22s cold) while the
    # same shape at chr2:100,000 returned instantly — and the slow ones then
    # exceeded the query time budget and were refused.
    #
    # Adding a lower bound turns it into a narrow range scan: the same query
    # bounded to a 1kb window returned in 2ms, roughly 1800x faster.
    #
    # The bound is only safe if it is at least as large as the longest variant
    # in the collection, because a long deletion can start well before the
    # queried position and still overlap it. Hence it is caller-supplied and
    # opt-in: omit it and the query stays exhaustive but slow.
    if max_variant_span is not None:
        lower = start - max_variant_span
        filters['start__gte'] = lower if lower > 0 else 0

    return filters
