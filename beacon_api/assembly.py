"""Assembly-identifier canonicalisation.

Deliberately free of Django / DRF / MongoEngine imports so the alias logic can
be unit-tested standalone (see ``beacon_api/test_assembly.py``) without a
settings module or a live MongoDB — the same arrangement as
``beacon_api/query_semantics.py``.

Why this module exists
----------------------
``hg38`` and ``GRCh38`` name the same genome build; so do ``hg19`` and
``GRCh37``. Only the vocabulary differs — UCSC vs GRC. The query path applied
the caller's spelling to Mongo as raw string equality while the validator
accepted all four spellings, so a caller using UCSC vocabulary matched nothing
and was told ``exists: false`` for a variant the panel holds.

That is the worst failure a discovery beacon has. A false negative is
indistinguishable from a true one, and the GA4GH verifier cannot catch it —
it checks envelope shape, and passed 17/17 throughout the period when position
queries were off by one base.

Two spellings, not one
----------------------
Canonicalising the *query* alone is not enough: which spelling is stored
depends on the ingest run that wrote the document. So a query resolves to
every known spelling of its build and matches with ``assembly_id__in``, the
same treatment ``reference_name`` already gets for the ``chr`` prefix
(``views_boolean.py:124``).
"""

#: Canonical GRC identifier -> every spelling that names the same build.
#: Canonical first; order is stable so query filters are reproducible.
ASSEMBLY_ALIASES = {
    'GRCh38': ('GRCh38', 'hg38'),
    'GRCh37': ('GRCh37', 'hg19'),
}

#: Lookup of every accepted spelling, casefolded, to its canonical form.
_CANONICAL_BY_SPELLING = {
    spelling.casefold(): canonical
    for canonical, spellings in ASSEMBLY_ALIASES.items()
    for spelling in spellings
}


class UnknownAssembly(ValueError):
    """Raised for an assembly this beacon cannot answer for.

    Refusing is deliberate. Dropping an unrecognised assembly and answering
    the remaining filters would return a confident boolean about a build the
    caller never asked about.
    """


def canonical_assembly(value):
    """Return the canonical GRC identifier for ``value``.

    Matching ignores case and surrounding whitespace, so ``HG38``, ``hg38``
    and ``  GRCh38 `` all resolve to ``GRCh38``.

    Raises ``UnknownAssembly`` for anything else, including None and blanks.
    """
    if value is None:
        raise UnknownAssembly('No assembly supplied')

    key = str(value).strip().casefold()
    if not key:
        raise UnknownAssembly('No assembly supplied')

    try:
        return _CANONICAL_BY_SPELLING[key]
    except KeyError:
        raise UnknownAssembly(
            f'Unknown assembly: {value}. This beacon answers for '
            f'{", ".join(sorted(ASSEMBLY_ALIASES))}.'
        ) from None


def assembly_query_values(value):
    """Every stored spelling that should match a query for ``value``.

    Feed this to ``assembly_id__in`` rather than comparing for equality, so a
    query is answered from documents written under either vocabulary.
    """
    return list(ASSEMBLY_ALIASES[canonical_assembly(value)])


def assembly_filter(value):
    """The Mongo filter fragment for an assembly query.

    Returns the ``__in`` form deliberately. Equality on the caller's raw
    spelling is what produced the false negatives this module exists to stop,
    so the shape is pinned by ``test_assembly.AssemblyFilter`` rather than
    left to a one-line call site.
    """
    return {'assembly_id__in': assembly_query_values(value)}
