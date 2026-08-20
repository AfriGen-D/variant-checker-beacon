"""What this beacon can and cannot answer, and how it says so.

Django-free by design, like ``query_semantics``, ``assembly`` and
``query_vocabulary``, so the rules are unit-testable without a settings module
or a live MongoDB.

Why this module exists
----------------------
``/datasets/{id}/{entry_type}`` returned a constant empty query envelope for
every input: HTTP 200, ``exists: false``. A dataset the catalogue reports as
holding 42 million variants answered "not found" for a locus inside it, under
a one-hour cache.

The view directly above that stub carries a comment recording exactly why this
is dangerous — returning the empty 200 envelope "made a MongoDB outage
indistinguishable from a genuine miss, so clients (and the Beacon Network
aggregator) would record an authoritative 'does not exist' for data we simply
could not read". The stub below it did that by construction, permanently.

So an unimplemented endpoint must answer **501 Not Implemented**, not a
boolean. "I cannot answer this" and "the answer is no" are different
statements, and only one of them is true here.
"""

#: Entry types for which per-dataset drill-down is actually implemented.
#: Empty today. Add an entry type here in the SAME commit that implements it —
#: never in advance, or the beacon resumes answering "no" for it.
DATASET_SCOPED_ENTRY_TYPES = frozenset()


def is_dataset_scope_supported(entry_type, supported=None):
    """Whether ``/datasets/{id}/{entry_type}`` can really answer."""
    if supported is None:
        supported = DATASET_SCOPED_ENTRY_TYPES
    return entry_type in supported


def unsupported_dataset_scope_message(dataset_id, entry_type):
    """The 501 message for an unimplemented per-dataset query.

    States that the beacon cannot answer, never that the data is absent, and
    points the caller at the endpoint that does work — otherwise a client that
    hits this has no route forward.
    """
    return (
        f'Per-dataset {entry_type} queries are not implemented. '
        f'This beacon cannot answer for dataset {dataset_id} on this endpoint; '
        f'it is not a statement about whether the data is present. '
        f'Query /api/{entry_type} instead, and filter by datasetIds.'
    )

# ── Assembly coverage ───────────────────────────────────────────────────────
#
# GRCh37 and hg19 are *known* assemblies: they pass validation, canonicalise
# correctly, and then match no stored data — so the beacon answered
# `exists: false` for a build it simply does not hold. A user reaches that in
# two clicks from the UI's assembly selector and gets an authoritative
# "not in the African panel" with no way to tell it from a true negative.
#
# Same defect as the dataset-scope stub above, one layer out.
#
# Coverage is DERIVED from the dataset catalogue rather than hard-coded, so it
# stays true on its own: load a GRCh37 dataset and the beacon starts answering
# for GRCh37 with no code change. Hard-coding it here would rot the first time
# the data changed, which is exactly how the UI's selector came to offer a
# build the beacon never held.


def served_assemblies(declared):
    """Canonical assemblies this beacon holds, from ``Dataset.assembly_id``."""
    from .assembly import canonical_assembly

    out = set()
    for value in declared or ():
        if not value:
            continue
        canonical = canonical_assembly(value)
        if canonical:
            out.add(canonical)
    return frozenset(out)


def is_assembly_served(assembly, served):
    """Whether the beacon holds data for ``assembly``.

    Compares canonically, so ``hg38`` is served by a dataset that spells its
    build ``GRCh38``. An empty catalogue serves nothing — it must not
    accidentally serve everything.
    """
    from .assembly import canonical_assembly

    canonical = canonical_assembly(assembly)
    return bool(canonical) and canonical in served


def unserved_assembly_message(assembly, served):
    """The 501 message for a build this beacon does not hold.

    Says the beacon cannot answer and names what it CAN answer for. It must
    never imply the variant is absent — that claim is the bug.
    """
    held = ", ".join(sorted(served)) if served else "no assemblies"
    return (
        f'This beacon holds no data for assembly {assembly}, so it cannot '
        f'answer for that build. This is not a statement about whether the '
        f'variant exists. Data held: {held}.'
    )
