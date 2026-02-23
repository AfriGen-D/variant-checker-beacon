from rest_framework.test import APITestCase
from rest_framework import status

class BeaconAPITests(APITestCase):
    def test_info_endpoint(self):
        response = self.client.get('/api/info')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_variants_endpoint(self):
        response = self.client.get('/api/g_variants')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_datasets_endpoint(self):
        response = self.client.get('/api/datasets')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_query_endpoint(self):
        # Example minimal query, adjust as needed for your schema
        payload = {
            "assemblyId": "GRCh38",
            "referenceName": "11",
            "start": 5227002,
            "referenceBases": "A",
            "alternateBases": "T"
        }
        response = self.client.post('/api/query', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])  # Accept 400 if validation fails 