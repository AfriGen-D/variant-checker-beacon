"""
The deployment environment that /api/info reports.

Free of Django so it can be unit-tested with plain unittest (see release.py).

``/api/info`` used to hard-code ``'environment': 'prod'``, so the development
server at api-beacon-dev.afrigen-d.dev advertised itself as production. The
value is now configured with ``BEACON_ENVIRONMENT``. Unset means ``prod`` so
existing production deployments are unchanged; an unrecognised value is an
error rather than a silent ``prod``, because a mistyped setting must not
relabel a development server as production.
"""

# The values the GA4GH Beacon v2 ``environment`` field allows.
ALLOWED_ENVIRONMENTS = ('prod', 'test', 'dev', 'staging')
DEFAULT_ENVIRONMENT = 'prod'


def resolve_environment(value):
    """Return the environment for ``value``, or raise ``ValueError`` if it is not one of the allowed values."""
    cleaned = (value or '').strip().lower()
    if not cleaned:
        return DEFAULT_ENVIRONMENT
    if cleaned not in ALLOWED_ENVIRONMENTS:
        raise ValueError(
            f"BEACON_ENVIRONMENT={value!r} is not valid; use one of "
            f"{', '.join(ALLOWED_ENVIRONMENTS)}"
        )
    return cleaned
