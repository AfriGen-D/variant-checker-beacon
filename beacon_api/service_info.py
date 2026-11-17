"""GA4GH service-info for /api/service-info.

/info stays the Beacon info envelope ({meta, response}). /service-info is the
GA4GH-wide discovery document a service registry reads: required id, name,
type {group, artifact, version}, organization {name, url} and version.
`version` is the running release stamped into the image (see release.py), so a
registry can tell deployments apart; `type.version` is the Beacon spec level.

Free of MongoEngine so it can be unit-tested without a database.
"""
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .release import get_release


def build_service_info(environ=None):
    return {
        'id': settings.BEACON_API_ID,
        'name': settings.BEACON_API_NAME,
        'type': {
            'group': 'org.ga4gh',
            'artifact': 'beacon',
            'version': settings.BEACON_API_VERSION,
        },
        'description': 'GA4GH Beacon v2 API - Public boolean discovery service',
        'organization': {
            'name': settings.BEACON_ORGANIZATION_NAME,
            'url': settings.BEACON_ORGANIZATION_URL,
        },
        'contactUrl': settings.BEACON_CONTACT_URL,
        'documentationUrl': settings.BEACON_WELCOME_URL,
        'environment': settings.BEACON_ENVIRONMENT,
        'version': get_release(environ),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def service_info(request):
    return Response(build_service_info())
