"""Normalise a Beacon v2 POST body into the flat shape the views query on.

Why this exists
---------------
Beacon v2 nests query parameters::

    {"query": {"requestParameters": {"referenceName": "1", "start": 12345},
               "requestedGranularity": "boolean"}}

The views build their Mongo query from TOP-LEVEL keys, and nothing in the app
ever read ``requestParameters``. So a spec-conformant POST produced a query with
no filters at all — measured on a real stack with 100 variants loaded, a body
naming the impossible locus chr7:999,999,999 returned ``exists: true`` with
``numTotalResults: 100``, identical to an empty body.

That is the project's central failure class: answering a broader question than
the one asked, with a 200 and no warning. ``beacon_api/filters.py`` refuses the
``filters`` parameter rather than silently widening a query for exactly this
reason; this module is the same judgement applied to the request envelope.

Django-free on purpose — pure dict manipulation, so it runs in the fast CI gate
alongside query_semantics, assembly and capabilities.
"""

#: Keys that live beside `requestParameters` inside `query` and are meaningful
#: to the views. Lifted so a nested body behaves like the equivalent GET.
_QUERY_SIBLINGS = ('requestedGranularity', 'filters', 'pagination', 'testMode',
                   'includeResultsetResponses', 'requestedSchemas')


def flatten_beacon_request(body):
    """Return `body` with `query.requestParameters` lifted to the top level.

    A flat body — a GET-style mapping, or a POST that already puts parameters
    at the top — is returned unchanged. A non-mapping is passed straight back
    so callers need no isinstance dance.

    A top-level key WINS over the same key nested inside `query`: an explicit
    top-level value is the caller being unambiguous, and silently overriding it
    would be the same silent-widening bug in a new place.
    """
    if not isinstance(body, dict):
        return body

    query = body.get('query')
    if not isinstance(query, dict):
        return body

    flat = {}

    params = query.get('requestParameters')
    if isinstance(params, dict):
        flat.update(params)

    for key in _QUERY_SIBLINGS:
        if key in query:
            flat[key] = query[key]

    # Top-level keys last so they win, and `query` itself is dropped — leaving
    # it in would let a later reader query on the raw envelope by accident.
    for key, value in body.items():
        if key != 'query':
            flat[key] = value

    return flat
