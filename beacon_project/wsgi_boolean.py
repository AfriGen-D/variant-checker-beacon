"""
WSGI entrypoint for Boolean mode.

Production runs this, not `beacon_project.wsgi` — the compose service sets
`command: gunicorn beacon_project.wsgi_boolean:application`. It existed only as
an untracked file on the host, so an image built from the repo had no such
module and gunicorn exited "Worker failed to boot" on start.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beacon_project.settings_boolean')
application = get_wsgi_application()
