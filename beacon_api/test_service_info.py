"""/service-info is a GA4GH service-info document, not a copy of /info (G3).

Before: /api/service-info returned the Beacon info envelope ({meta, response})
so a GA4GH service registry looking for `type.group`/`type.artifact` found
nothing. The GA4GH service-info schema requires id, name, type
{group, artifact, version}, organization {name, url} and version.

Needs Django + DRF (not mongoengine):

    python3 -m unittest beacon_api.test_service_info -v
"""
import pathlib
import unittest

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        SECRET_KEY='test-only',
        ALLOWED_HOSTS=['*'],
        BEACON_API_ID='org.test.beacon',
    )
    import django

    django.setup()

from django.test import RequestFactory, SimpleTestCase, override_settings  # noqa: E402

from beacon_api.service_info import build_service_info, service_info  # noqa: E402

BEACON = override_settings(
    BEACON_API_ID='org.test.beacon',
    BEACON_API_NAME='Test Beacon',
    BEACON_API_VERSION='v2.0.0',
    BEACON_ENVIRONMENT='test',
    BEACON_ORGANIZATION_NAME='Test Org',
    BEACON_ORGANIZATION_URL='https://org.test',
    BEACON_CONTACT_URL='mailto:help@org.test',
    BEACON_WELCOME_URL='https://org.test/beacon',
)
REQUIRED = {'id', 'name', 'type', 'organization', 'version'}


@BEACON
class BuildServiceInfoTests(SimpleTestCase):
    def test_every_required_ga4gh_field_is_present(self):
        doc = build_service_info({'BEACON_RELEASE': 'v1.1.14'})
        self.assertTrue(REQUIRED <= set(doc), doc)
        self.assertEqual(doc['type'], {'group': 'org.ga4gh', 'artifact': 'beacon', 'version': 'v2.0.0'})
        self.assertEqual(doc['organization'], {'name': 'Test Org', 'url': 'https://org.test'})

    def test_it_is_not_the_beacon_envelope(self):
        doc = build_service_info({})
        self.assertNotIn('meta', doc)
        self.assertNotIn('response', doc)

    def test_identity_comes_from_settings(self):
        doc = build_service_info({})
        self.assertEqual(doc['id'], 'org.test.beacon')
        self.assertEqual(doc['name'], 'Test Beacon')
        self.assertEqual(doc['environment'], 'test')
        self.assertEqual(doc['contactUrl'], 'mailto:help@org.test')
        self.assertEqual(doc['documentationUrl'], 'https://org.test/beacon')

    def test_version_is_the_running_release(self):
        self.assertEqual(build_service_info({'BEACON_RELEASE': 'v1.1.14'})['version'], 'v1.1.14')

    def test_an_unstamped_image_says_unknown_not_a_spec_version(self):
        self.assertEqual(build_service_info({})['version'], 'unknown')
        self.assertEqual(build_service_info({'BEACON_RELEASE': '  '})['version'], 'unknown')


@BEACON
@override_settings(REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES': [], 'UNAUTHENTICATED_USER': None})
class ServiceInfoViewTests(SimpleTestCase):
    def test_get_answers_200_with_the_document(self):
        response = service_info(RequestFactory().get('/api/service-info'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(REQUIRED <= set(response.data))


class RouteTests(unittest.TestCase):
    def test_boolean_urls_route_service_info_to_the_ga4gh_view(self):
        src = (pathlib.Path(__file__).resolve().parent / 'urls_boolean.py').read_text()
        self.assertIn("path('service-info', service_info.service_info", src)
        self.assertNotIn("path('service-info', views_boolean.beacon_info_boolean", src)


if __name__ == '__main__':
    unittest.main()
