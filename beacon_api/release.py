"""
The release of the beacon code that this container is running.

Deliberately free of Django, DRF and MongoEngine so it can be unit-tested with
plain unittest, and imported from anywhere without pulling in settings.

Why this is not ``settings.BEACON_API_VERSION``: that value is
``config('BEACON_API_VERSION', default='v2.0.0')``
(``beacon_project/settings_boolean.py:226``) — it describes the GA4GH spec
level, it is operator-settable, and it is constant across releases. On
2026-08-19 production and a deployment three and a half months behind it
returned the identical string from ``/api/health``, which is precisely why
three instances drifted with nothing reporting it.
"""
import os

UNKNOWN_RELEASE = 'unknown'


def get_release(environ=None):
    """
    Return the release tag stamped into the image at build time.

    ``environ`` is injectable for tests; production passes nothing and reads
    ``os.environ``. Returns ``UNKNOWN_RELEASE`` when the stamp is missing or
    blank, never an empty string — a consumer should not have to tell an
    unstamped image apart from a missing field.
    """
    env = os.environ if environ is None else environ
    return (env.get('BEACON_RELEASE') or '').strip() or UNKNOWN_RELEASE
