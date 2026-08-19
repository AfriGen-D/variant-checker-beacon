"""Controlled vocabularies for query parameters.

Deliberately free of Django / DRF / MongoEngine imports so the vocabulary logic
can be unit-tested standalone (``beacon_api/test_query_vocabulary.py``) without
a settings module or a live MongoDB — the same arrangement as
``query_semantics.py`` and ``assembly.py``.

Why this module exists
----------------------
``variantType`` and ``sex`` were both declared, validated, and then never
applied to the query. The beacon answered a broader question than the one it
was asked and returned 200 without saying so.

``beacon_api/filters.py`` already names that failure class and refuses the
``filters`` parameter rather than ignoring it. These vocabularies apply the
same judgement: **canonicalise and apply, or refuse — never drop.**

There was a second defect layered on the first. The old allow-list contained
``SNP`` while the ingest transform writes ``SNV``
(``vcf_transform/vcf_to_beacon.py:436``), so the correct term, the stored value
and the value ``docs/TESTING.md`` advertises were all rejected with a 400 —
while ``DEL`` was accepted and then discarded. Both spellings now resolve to the
stored ``SNV``.
"""

#: Canonical stored value -> every accepted spelling.
VARIANT_TYPE_ALIASES = {
    'SNV': ('SNV', 'SNP'),
    'DEL': ('DEL',),
    'INS': ('INS',),
    'DUP': ('DUP',),
    'INV': ('INV',),
    'CNV': ('CNV',),
    'DUP:TANDEM': ('DUP:TANDEM',),
    'DEL:ME': ('DEL:ME',),
    'INS:ME': ('INS:ME',),
}

_VARIANT_TYPE_BY_SPELLING = {
    spelling.casefold(): canonical
    for canonical, spellings in VARIANT_TYPE_ALIASES.items()
    for spelling in spellings
}

#: Beacon v2 / Phenopackets sex values.
SEX_VALUES = ('MALE', 'FEMALE', 'OTHER', 'UNKNOWN')

_SEX_BY_SPELLING = {v.casefold(): v for v in SEX_VALUES}


class UnknownVariantType(ValueError):
    """Raised for a variant type this beacon cannot answer for."""


class UnknownSex(ValueError):
    """Raised for a sex value this beacon cannot answer for."""


def _canonicalise(value, lookup, error, what, known):
    if value is None:
        raise error(f'No {what} supplied')
    key = str(value).strip().casefold()
    if not key:
        raise error(f'No {what} supplied')
    try:
        return lookup[key]
    except KeyError:
        raise error(
            f'Unknown {what}: {value}. This beacon answers for '
            f'{", ".join(known)}.'
        ) from None


def canonical_variant_type(value):
    """Return the stored variant-type value for ``value``.

    ``SNP`` resolves to ``SNV``. Matching ignores case and surrounding
    whitespace. Raises ``UnknownVariantType`` for anything else — including
    blanks, which must not be read as "no filter requested".
    """
    return _canonicalise(
        value, _VARIANT_TYPE_BY_SPELLING, UnknownVariantType,
        'variant type', sorted(VARIANT_TYPE_ALIASES),
    )


def variant_type_filter(value):
    """The Mongo filter fragment for a variant-type query.

    Emitting this at all is the point — the defect was that the parameter was
    validated and then never reached the query.

    It emits the ``__in`` form rather than equality because which spelling is
    STORED depends on who wrote the document: the ingest transform writes
    ``SNV`` (``vcf_to_beacon.py:436``) while the bundled fixture writes ``SNP``
    (``load_boolean_test_data.py:52``). Filtering on one canonical value would
    return a confident false negative against data written under the other —
    reintroducing this module's own defect from the opposite side. Same
    treatment ``assembly_id`` and ``reference_name`` already get.
    """
    return {'variant_type__in': list(VARIANT_TYPE_ALIASES[canonical_variant_type(value)])}


def canonical_sex(value):
    """Return the canonical sex value for ``value``.

    Raises ``UnknownSex`` rather than dropping an unrecognised value, which
    turned an individuals query into "do you have anyone at all".
    """
    return _canonicalise(
        value, _SEX_BY_SPELLING, UnknownSex, 'sex', SEX_VALUES,
    )


def dataset_id_list(value):
    """Normalise ``datasetIds`` to a list of ids.

    ``datasetIds`` is declared as a list, but ``request.GET.dict()`` keeps a
    single value per key, so a GET caller could never form one and the
    parameter rejected every request that used it. Accepting the
    comma-separated form is how a client naturally writes a list in a URL.

    Returns ``[]`` for an absent or blank value, which the caller reads as
    "no dataset filter requested" — not as "match a dataset with a blank id".
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value).split(',')
    return [s for s in (str(i).strip() for i in items) if s]
