"""Reject query parameters this beacon cannot honour (review 2026-10-22, G1).

Standalone by design -- no Django, DRF or MongoEngine imports -- like
``beacon_api/filters.py``, so it runs in the fast CI gate.

The bug this replaces
---------------------
``BeaconQuerySerializer`` declares a fixed set of fields and DRF discards the
rest. ``geneId=HBB`` -- or ``geneId=NOSUCHGENE_ZZZ`` -- therefore reduced to the
default ``assemblyId=GRCh38`` query and was answered ``exists: true`` over the
whole 42-million-variant panel. ``docs/TESTING.md`` advertised ``geneId``,
``aminoacidChanges``, ``variantMinLength`` and ``variantMaxLength``; none is
implemented. The same silent drop applied to any misspelt name, which may have
been a narrowing parameter.

Why reject rather than implement
--------------------------------
Variants are not annotated with genes or protein changes in this beacon's
schema (see ``beacon_api/models.py``), so there is nothing to query on. A 400
that names the parameter is the honest answer; a 200 over the whole panel is
the answer to a different question.

Why unknown names are rejected too
----------------------------------
The failure is identical whether the name is a documented-but-unimplemented
spec parameter or a typo of a real one (``referencename``). Both would widen
the query silently. The envelope keys the Beacon Network and Beacon v2 clients
send as a matter of course are listed in ``ENVELOPE_KEYS`` and pass.
"""

#: Fields ``BeaconQuerySerializer`` understands (kept in step with it by
#: test_unsupported_params_validate).
IMPLEMENTED = frozenset({
    'referenceName', 'chromosome', 'start', 'end', 'position',
    'referenceBases', 'alternateBases', 'variantType', 'assemblyId',
    'datasetIds', 'requestedGranularity', 'skip', 'limit',
})

#: What ``individual_query_boolean`` reads (plus pagination, parsed separately).
INDIVIDUAL_IMPLEMENTED = frozenset({'sex', 'diseaseCode', 'skip', 'limit'})

#: Keys that carry no query semantics for this beacon, or are judged by their
#: own module before this runs. ``filters`` has a dedicated message in
#: ``beacon_api/filters.py``; ``pagination`` is the nested spelling of
#: skip/limit; the rest are Beacon v2 envelope fields and client cache-busters.
ENVELOPE_KEYS = frozenset({
    'filters', 'pagination', 'includeResultsetResponses', 'testMode',
    'requestedSchemas', '_t', 'format',
})

#: Parameters that must carry a single integer, not a list.
SCALAR_COORDINATES = ('start', 'end')

MAX_ECHOED_NAMES = 5
MAX_ECHOED_NAME_LENGTH = 40


class UnsupportedParameters(ValueError):
    """The request names parameters this beacon would otherwise drop."""


def _describe(names):
    shown = [str(n)[:MAX_ECHOED_NAME_LENGTH] for n in names[:MAX_ECHOED_NAMES]]
    if len(names) > MAX_ECHOED_NAMES:
        shown.append('...')
    return ', '.join(shown)


def reject_unsupported_params(params, allowed=IMPLEMENTED):
    """Raise :class:`UnsupportedParameters` if `params` names anything the
    query path would drop. Call before the serializer sees the request.

    `allowed` is the set of names the calling endpoint reads; the default is
    the variant query."""
    if not isinstance(params, dict):
        return

    offenders = sorted(k for k in params if k not in allowed and k not in ENVELOPE_KEYS)
    if allowed is IMPLEMENTED:
        supported = (
            'referenceName, start, end, referenceBases, alternateBases, '
            'variantType, assemblyId, datasetIds, requestedGranularity, skip, '
            'limit (start and end take one integer each, not a list)'
        )
    else:
        supported = ', '.join(sorted(allowed))
    for name in (SCALAR_COORDINATES if allowed is IMPLEMENTED else ()):
        if isinstance(params.get(name), (list, tuple)):
            offenders.append(name)

    if not offenders:
        return
    raise UnsupportedParameters(
        'This beacon does not support the parameter(s): '
        f'{_describe(offenders)}. They would be ignored and the answer would '
        'cover the whole panel rather than the subset you asked for, so the '
        f'request is refused. Supported here: {supported}.'
    )
