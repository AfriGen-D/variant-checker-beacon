# Testing Guide - GA4GH Beacon v2 API

Comprehensive testing documentation for the Beacon v2 API implementation, inspired by the [EGA Beacon v2 Reference Implementation](https://github.com/EGA-archive/beacon2-ri-api) which maintains 313+ unit tests with 100% code coverage.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Quick Start](#quick-start)
- [Test Infrastructure](#test-infrastructure)
- [Query Examples & Test Cases](#query-examples--test-cases)
- [Unit Testing](#unit-testing)
- [Integration Testing](#integration-testing)
- [Security Testing](#security-testing)
- [Performance Testing](#performance-testing)
- [Test Data Management](#test-data-management)
- [CI/CD Integration](#cicd-integration)
- [Coverage & Quality Metrics](#coverage--quality-metrics)
- [Troubleshooting](#troubleshooting)

## Testing Philosophy

This Beacon v2 implementation follows a comprehensive testing strategy inspired by the [EGA Beacon v2 Public Instance](https://github.com/EGA-archive/beacon2-pi-api), which maintains production-grade test coverage and performance benchmarks.

### Test Pyramid

```
    /\     E2E Tests (10%)
   /  \    - Full workflow testing
  /────\   Integration Tests (20%)
 /      \  - Component interactions
/────────\ Unit Tests (70%)
           - Fast, isolated tests
```

**Distribution:**
- **Unit Tests (70%)**: Fast, isolated component tests
- **Integration Tests (20%)**: API endpoints, database queries, cache integration
- **E2E Tests (10%)**: Complete workflow validation

### Dual-Mode Testing

This implementation supports two distinct operational modes:

| Mode | Access | Response | Authentication | Rate Limit |
|------|--------|----------|----------------|------------|
| **Boolean** | Public | YES/NO only | None | 50/hour |
| **Secure** | Authenticated | Full records | JWT required | Higher |

Each mode requires distinct test scenarios and security considerations.

### Quality Targets

Based on EGA Beacon v2 PI benchmarks:

| Metric | Target | Measurement |
|--------|--------|-------------|
| Code Coverage | 80% min, 100% ideal | Line coverage |
| Response Time | <100ms | 95th percentile |
| Throughput | 100 req/s | Sustained load |
| Test Execution | <5 minutes | Full suite |

## Quick Start

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=beacon_api --cov-report=html --cov-report=term

# Run specific test suite
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests
pytest tests/security/                # Security tests

# Run specific test file
pytest tests/unit/test_validators.py

# Run specific test
pytest tests/unit/test_validators.py::TestChromosomeValidator::test_valid_numeric_chromosome

# Run tests in parallel (faster)
pytest -n auto

# View coverage report
open htmlcov/index.html
```

### Docker Testing Environment

```bash
# Start test environment
docker-compose -f docker-compose-test.yml up -d

# Run tests in container
docker-compose -f docker-compose-test.yml run --rm test-runner pytest

# Run specific test suite
docker-compose -f docker-compose-test.yml run --rm test-runner pytest tests/integration/

# Stop test environment
docker-compose -f docker-compose-test.yml down
```

### Load Testing

```bash
# Install Locust
pip install locust

# Run load tests
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Open browser to http://localhost:8089 to configure and start test
```

## Test Infrastructure

### Required Dependencies

```bash
# requirements-test.txt
pytest==7.4.3
pytest-django==4.7.0
pytest-cov==4.1.0
pytest-mock==3.12.0
pytest-asyncio==0.21.1
pytest-xdist==3.5.0          # Parallel execution
factory-boy==3.3.0           # Test fixtures
faker==20.1.0                # Fake data generation
locust==2.20.0               # Load testing
responses==0.24.1            # HTTP mocking
freezegun==1.4.0             # Time mocking
```

### Test Configuration Files

**pytest.ini**:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = beacon_project.settings_test
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --strict-markers
    --tb=short
    --cov=beacon_api
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    performance: Performance tests
    slow: Slow-running tests
testpaths = tests
```

**.coveragerc**:
```ini
[run]
source = beacon_api
omit =
    */migrations/*
    */tests/*
    */venv/*
    */__pycache__/*
    */settings*.py

[report]
precision = 2
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

**conftest.py** (test fixtures):
```python
import pytest
from mongoengine import connect, disconnect
from django.conf import settings
from rest_framework.test import APIClient


@pytest.fixture(scope='session')
def django_db_setup():
    """Setup test database"""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


@pytest.fixture(scope='function')
def mongo_db():
    """Setup MongoDB test database"""
    disconnect()
    connect('beacon_test', host='mongomock://localhost')
    yield
    disconnect()


@pytest.fixture
def api_client():
    """DRF API client"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    """Authenticated API client for secure mode"""
    token = generate_test_jwt()
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client


@pytest.fixture
def sample_variants(mongo_db):
    """Load sample variant data"""
    from beacon_api.models import GenomicVariant
    variants = [
        GenomicVariant(
            id="var-1",
            assembly_id="GRCh38",
            reference_name="17",
            start=7577120,
            reference_bases="G",
            alternate_bases="A",
        ),
        # Add more test variants
    ]
    GenomicVariant.objects.insert(variants)
    return variants
```

### Test Database Setup

**MongoDB Test Instance**:
```bash
# Option 1: Use mongomock (in-memory, faster)
pip install mongomock

# Option 2: Use real MongoDB test instance
docker run -d --name mongodb-test -p 27018:27017 mongo:5.0

# Connect to test database in settings_test.py
MONGODB_HOST = 'localhost'
MONGODB_PORT = 27018
MONGODB_NAME = 'beacon_test'
```

**Redis Test Instance**:
```bash
# Start Redis test instance
docker run -d --name redis-test -p 6380:6379 redis:6

# Configure in settings_test.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6380/0',
    }
}
```

## Query Examples & Test Cases

Comprehensive query examples based on [EGA Beacon v2 RI](https://github.com/EGA-archive/beacon2-ri-api) and [GA4GH Beacon v2 specification](https://docs.genomebeacons.org/).

### Genomic Variant Queries

#### Simple SNV Query (GET)

**Request**:
```bash
curl "http://localhost:8000/api/g_variants?\
assemblyId=GRCh38&\
referenceName=17&\
start=7577120&\
referenceBases=G&\
alternateBases=A"
```

**Boolean Mode Response**:
```json
{
  "meta": {
    "apiVersion": "2.0",
    "beaconId": "org.h3abionet.beacon"
  },
  "response": {
    "exists": true
  }
}
```

**Secure Mode Response**:
```json
{
  "meta": {
    "apiVersion": "2.0",
    "returnedGranularity": "record"
  },
  "response": {
    "exists": true,
    "numTotalResults": 15,
    "resultSets": [
      {
        "id": "dataset-1",
        "exists": true,
        "resultsCount": 15,
        "results": [
          {
            "variantInternalId": "var-12345",
            "variation": {
              "location": {
                "interval": {
                  "start": {"value": 7577120},
                  "end": {"value": 7577121}
                },
                "sequence_id": "refseq:NC_000017.11"
              },
              "referenceBases": "G",
              "alternateBases": "A"
            },
            "caseLevelData": [
              {
                "biosampleId": "sample-001",
                "individualId": "ind-001"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### Range Query (POST)

**Request**:
```bash
curl -X POST http://localhost:8000/api/g_variants \
  -H "Content-Type: application/json" \
  -d '{
    "meta": {"apiVersion": "2.0"},
    "query": {
      "requestParameters": {
        "alternateBases": "G",
        "referenceBases": "A",
        "start": [16050074],
        "end": [16050568],
        "referenceName": "22",
        "assemblyId": "GRCh37"
      },
      "includeResultsetResponses": "HIT",
      "pagination": {"skip": 0, "limit": 10},
      "requestedGranularity": "record"
    }
  }'
```

#### Bracket Query (Structural Variants)

Find deletions overlapping a region:

```bash
curl "http://localhost:8000/api/g_variants?\
referenceName=NC_000017.11&\
variantType=DEL&\
start=5000000,7676592&\
end=7669607,10000000"
```

**Interpretation**: Find deletions where:
- Start position is between 5,000,000 and 7,676,592
- End position is between 7,669,607 and 10,000,000

#### Gene-Based Query

```bash
curl "http://localhost:8000/api/g_variants?\
assemblyId=GRCh38&\
geneId=EIF4A1&\
variantMaxLength=1000000&\
variantType=DEL"
```

**Finds**: All deletions in the EIF4A1 gene up to 1Mb in length.

#### Amino Acid Change Query

```bash
curl "http://localhost:8000/api/g_variants?\
assemblyId=GRCh38&\
geneId=BRCA1&\
aminoacidChanges=M734V"
```

**Finds**: Variants causing the M734V amino acid substitution in BRCA1.

### Individual Queries

#### Ontology Filter Query

```bash
curl "http://localhost:8000/api/individuals?\
filters=NCIT:C16576,NCIT:C42331"
```

**NCIT:C16576** = Female
**NCIT:C42331** = Breast Carcinoma

**Finds**: Female individuals with breast carcinoma.

#### Phenoclinic Query (POST)

```bash
curl -X POST http://localhost:8000/api/individuals \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "filters": [
        {"id": "ethnicity=NCIT:C16352"},
        {"id": "geographicOrigin=England"},
        {"id": "Weight>50"},
        {"id": "Height-standing>150"}
      ],
      "requestedGranularity": "count"
    }
  }'
```

#### Disease-Based Query

```bash
curl "http://localhost:8000/api/individuals?\
filters=diseases.diseaseCode.label=asthma"
```

### Biosample Queries

#### Tissue Type Filter (POST)

```bash
curl -X POST http://localhost:8000/api/biosamples \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "filters": [
        {
          "id": "UBERON:0000178",
          "scope": "biosample",
          "includeDescendantTerms": false
        }
      ],
      "requestedGranularity": "count"
    }
  }'
```

**UBERON:0000178** = Blood sample

#### Multiple Filters with Descendant Terms

```bash
curl -X POST http://localhost:8000/api/biosamples \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "filters": [
        {
          "id": "NCIT:C16576",
          "scope": "individual",
          "includeDescendantTerms": false
        },
        {
          "id": "UBERON:0000178",
          "scope": "biosample",
          "includeDescendantTerms": true
        }
      ]
    }
  }'
```

### Query Parameter Reference

#### Genomic Variant Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| assemblyId | string | Yes | Reference genome assembly | GRCh38, GRCh37, hg38 |
| referenceName | string | Yes | Chromosome identifier | 1, 17, X, Y, MT, NC_000017.11 |
| start | integer/array | Yes | Start position(s) | 7577120, [5000000, 7676592] |
| end | integer/array | No | End position(s) | 7578641, [7669607, 10000000] |
| referenceBases | string | No | Reference allele | G, A, ATCG |
| alternateBases | string | No | Alternate allele | T, C, -, ATCG |
| variantType | string | No | Type of variant | SNV, DEL, DUP, INS, CNV |
| geneId | string | No | Gene identifier (HGNC) | EIF4A1, BRCA1, TP53 |
| aminoacidChanges | string | No | Protein change | M734V, R123*, p.Arg123Ter |
| variantMinLength | integer | No | Minimum variant length (bp) | 1000 |
| variantMaxLength | integer | No | Maximum variant length (bp) | 1000000 |

#### Response Granularity Options

| Granularity | Description | Boolean Mode | Secure Mode | Use Case |
|-------------|-------------|--------------|-------------|----------|
| boolean | YES/NO only | ✅ Default | ✅ Available | Public discovery |
| count | Number of results | ❌ Not allowed | ✅ Available | Aggregate statistics |
| record | Full records | ❌ Not allowed | ✅ Available | Detailed analysis |

#### Pagination Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| skip | integer | 0 | Number of results to skip |
| limit | integer | 10 | Maximum results to return |

**Example**:
```json
{
  "pagination": {
    "skip": 0,
    "limit": 100
  }
}
```

## Unit Testing

Unit tests verify individual components in isolation.

### Model Tests

Test MongoEngine document models:

```python
# tests/unit/test_models.py
import pytest
from beacon_api.models import GenomicVariant, Individual, Biosample


class TestGenomicVariantModel:
    def test_create_variant(self, mongo_db):
        variant = GenomicVariant(
            id="var-test-001",
            assembly_id="GRCh38",
            reference_name="17",
            start=7577120,
            reference_bases="G",
            alternate_bases="A",
        )
        variant.save()

        assert GenomicVariant.objects.count() == 1
        assert variant.reference_name == "17"

    def test_variant_validation(self, mongo_db):
        with pytest.raises(ValidationError):
            variant = GenomicVariant(
                id="var-test-002",
                # Missing required fields
            )
            variant.validate()

    def test_variant_position_range(self, mongo_db):
        variant = GenomicVariant(
            id="var-test-003",
            assembly_id="GRCh38",
            reference_name="1",
            start=1000000,
            end=1000010,
            reference_bases="ATCGATCGAT",
            alternate_bases="A",
        )
        variant.save()

        assert variant.variant_type == "DEL"
        assert variant.length == 10
```

### Validator Tests

Test input validation and sanitization:

```python
# tests/unit/test_validators.py
import pytest
from beacon_api.validators import (
    validate_chromosome,
    validate_position,
    validate_assembly_id,
    validate_bases,
)
from rest_framework.exceptions import ValidationError


class TestChromosomeValidator:
    def test_valid_numeric_chromosome(self):
        assert validate_chromosome("1") == "1"
        assert validate_chromosome("22") == "22"

    def test_valid_sex_chromosomes(self):
        assert validate_chromosome("X") == "X"
        assert validate_chromosome("Y") == "Y"

    def test_valid_mitochondrial(self):
        assert validate_chromosome("MT") == "MT"
        assert validate_chromosome("M") == "M"

    def test_refseq_format(self):
        assert validate_chromosome("NC_000017.11") == "NC_000017.11"

    def test_invalid_chromosome_raises_error(self):
        with pytest.raises(ValidationError):
            validate_chromosome("999")
        with pytest.raises(ValidationError):
            validate_chromosome("invalid")
        with pytest.raises(ValidationError):
            validate_chromosome("chr1")  # chr prefix not allowed


class TestPositionValidator:
    def test_valid_position(self):
        assert validate_position("1000000") == 1000000
        assert validate_position(1000000) == 1000000

    def test_negative_position_raises_error(self):
        with pytest.raises(ValidationError):
            validate_position("-1")

    def test_too_large_position_raises_error(self):
        with pytest.raises(ValidationError):
            validate_position("999999999999")  # Beyond max chromosome length

    def test_non_integer_raises_error(self):
        with pytest.raises(ValidationError):
            validate_position("abc")


class TestAssemblyValidator:
    def test_valid_assemblies(self):
        assert validate_assembly_id("GRCh38") == "GRCh38"
        assert validate_assembly_id("GRCh37") == "GRCh37"
        assert validate_assembly_id("hg38") == "hg38"

    def test_invalid_assembly_raises_error(self):
        with pytest.raises(ValidationError):
            validate_assembly_id("invalid_assembly")


class TestBasesValidator:
    def test_valid_bases(self):
        assert validate_bases("A") == "A"
        assert validate_bases("ATCG") == "ATCG"

    def test_deletion_representation(self):
        assert validate_bases("-") == "-"
        assert validate_bases("") == "-"  # Empty string = deletion

    def test_invalid_bases_raises_error(self):
        with pytest.raises(ValidationError):
            validate_bases("ATZ")  # Invalid nucleotide
        with pytest.raises(ValidationError):
            validate_bases("123")  # Numbers not allowed
```

### Serializer Tests

Test DRF serializers:

```python
# tests/unit/test_serializers.py
import pytest
from beacon_api.serializers import (
    GenomicVariantSerializer,
    IndividualSerializer,
    BiosampleSerializer,
)


class TestGenomicVariantSerializer:
    def test_serialize_variant(self, sample_variants):
        variant = sample_variants[0]
        serializer = GenomicVariantSerializer(variant)

        data = serializer.data
        assert data['variantInternalId'] == variant.id
        assert data['variation']['referenceBases'] == 'G'
        assert data['variation']['alternateBases'] == 'A'

    def test_deserialize_variant_data(self):
        data = {
            'id': 'var-new-001',
            'assembly_id': 'GRCh38',
            'reference_name': '1',
            'start': 1000000,
            'reference_bases': 'A',
            'alternate_bases': 'T',
        }
        serializer = GenomicVariantSerializer(data=data)
        assert serializer.is_valid()
        variant = serializer.save()
        assert variant.id == 'var-new-001'
```

### Middleware Tests

Test rate limiting and caching middleware:

```python
# tests/unit/test_middleware.py
import pytest
from django.test import RequestFactory
from beacon_api.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    def test_rate_limit_allows_within_limit(self, rf):
        middleware = RateLimitMiddleware(get_response=lambda r: None)
        request = rf.get('/api/g_variants')

        # First 50 requests should succeed
        for i in range(50):
            response = middleware(request)
            assert response.status_code != 429

    def test_rate_limit_blocks_after_limit(self, rf):
        middleware = RateLimitMiddleware(get_response=lambda r: None)
        request = rf.get('/api/g_variants')

        # Exhaust rate limit
        for i in range(50):
            middleware(request)

        # 51st request should be blocked
        response = middleware(request)
        assert response.status_code == 429
```

## Integration Testing

Integration tests verify component interactions and API behavior.

### API Endpoint Tests (Boolean Mode)

```python
# tests/integration/test_boolean_api.py
import pytest
from rest_framework.test import APITestCase


class TestBooleanVariantAPI(APITestCase):
    def setUp(self):
        # Load test fixtures
        self.load_test_variants()

    def test_simple_snv_query_returns_boolean(self):
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '17',
                'start': '7577120',
                'referenceBases': 'G',
                'alternateBases': 'A'
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'response' in data
        assert 'exists' in data['response']
        assert isinstance(data['response']['exists'], bool)

        # Boolean mode should NOT return counts or records
        assert 'numTotalResults' not in data['response']
        assert 'resultSets' not in data['response']

    def test_range_query(self):
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '1',
                'start': '1000000',
                'end': '2000000',
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['response']['exists'] in [True, False]

    def test_query_with_invalid_chromosome_returns_400(self):
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '999',  # Invalid
                'start': '1000000',
            }
        )

        assert response.status_code == 400

    def test_missing_required_parameters_returns_400(self):
        response = self.client.get('/api/g_variants')
        assert response.status_code == 400


class TestBooleanIndividualAPI(APITestCase):
    def test_ontology_filter_query(self):
        response = self.client.get(
            '/api/individuals',
            {'filters': 'NCIT:C16576,NCIT:C42331'}
        )

        assert response.status_code == 200
        data = response.json()
        assert 'exists' in data['response']
```

### API Endpoint Tests (Secure Mode)

```python
# tests/integration/test_secure_api.py
import pytest
from rest_framework.test import APITestCase


class TestSecureVariantAPI(APITestCase):
    def setUp(self):
        self.load_test_variants()
        self.authenticate()

    def test_variant_query_returns_full_records(self):
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '17',
                'start': '7577120',
                'referenceBases': 'G',
                'alternateBases': 'A'
            },
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['response']['exists'] == True
        assert 'numTotalResults' in data['response']
        assert 'resultSets' in data['response']

        # Check record structure
        results = data['response']['resultSets'][0]['results']
        assert len(results) > 0
        assert 'variantInternalId' in results[0]
        assert 'variation' in results[0]

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get('/api/g_variants')
        assert response.status_code == 401

    def test_query_with_pagination(self):
        response = self.client.post(
            '/api/g_variants',
            {
                'query': {
                    'requestParameters': {
                        'assemblyId': 'GRCh38',
                        'referenceName': '1',
                        'start': [1000000],
                        'end': [2000000]
                    },
                    'pagination': {
                        'skip': 0,
                        'limit': 10
                    }
                }
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )

        assert response.status_code == 200
        results = response.json()['response']['resultSets'][0]['results']
        assert len(results) <= 10
```

### Cache Integration Tests

```python
# tests/integration/test_caching.py
import pytest
from django.core.cache import cache
from django.test import TestCase


class TestQueryCaching(TestCase):
    def setUp(self):
        cache.clear()
        self.load_test_variants()

    def test_query_results_are_cached(self):
        # First query - cache miss
        response1 = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
        )

        # Second identical query - cache hit (should be faster)
        response2 = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
        )

        assert response1.json() == response2.json()

        # Check cache was used
        cache_key = self.generate_cache_key(
            assemblyId='GRCh38', referenceName='1', start='1000000'
        )
        assert cache.get(cache_key) is not None

    def test_cache_respects_ttl(self):
        cache_key = 'test_key'
        cache.set(cache_key, 'test_value', timeout=1)

        assert cache.get(cache_key) == 'test_value'

        import time
        time.sleep(2)

        assert cache.get(cache_key) is None
```

### Rate Limiting Integration Tests

```python
# tests/integration/test_rate_limiting.py
import pytest
from django.test import TestCase


class TestRateLimiting(TestCase):
    def test_rate_limit_enforcement(self):
        # Make 50 requests (at limit)
        for i in range(50):
            response = self.client.get(
                '/api/g_variants',
                {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
            )
            assert response.status_code == 200

        # 51st request should be rate limited
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
        )
        assert response.status_code == 429
        assert 'rate limit exceeded' in response.json()['error'].lower()

    def test_rate_limit_per_ip(self):
        # Requests from different IPs should have separate limits
        response1 = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'},
            REMOTE_ADDR='192.168.1.1'
        )

        response2 = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'},
            REMOTE_ADDR='192.168.1.2'
        )

        assert response1.status_code == 200
        assert response2.status_code == 200
```

## Security Testing

Security tests verify protection against common vulnerabilities and ensure authentication/authorization work correctly.

### Input Validation Tests

```python
# tests/security/test_input_validation.py
import pytest
from django.test import TestCase


class TestSQLInjectionPrevention(TestCase):
    """Test protection against SQL injection (though we use MongoDB)"""

    def test_sql_injection_in_chromosome(self):
        malicious_input = "1' OR '1'='1"
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': malicious_input,
                'start': '1000000'
            }
        )
        assert response.status_code == 400

    def test_sql_injection_in_gene_id(self):
        malicious_input = "BRCA1'; DROP TABLE variants; --"
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'geneId': malicious_input}
        )
        assert response.status_code == 400


class TestXSSPrevention(TestCase):
    """Test protection against Cross-Site Scripting"""

    def test_xss_in_filter_parameter(self):
        malicious_input = "<script>alert('XSS')</script>"
        response = self.client.get(
            '/api/individuals',
            {'filters': malicious_input}
        )
        assert response.status_code == 400

        # Ensure script is not echoed back in response
        assert '<script>' not in response.content.decode()


class TestCommandInjectionPrevention(TestCase):
    """Test protection against command injection"""

    def test_command_injection_in_position(self):
        malicious_input = "1000000; cat /etc/passwd"
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '1',
                'start': malicious_input
            }
        )
        assert response.status_code == 400


class TestBoundaryValidation(TestCase):
    """Test boundary conditions and edge cases"""

    def test_negative_position(self):
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '-1'}
        )
        assert response.status_code == 400

    def test_position_exceeds_chromosome_length(self):
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '999999999999'}
        )
        assert response.status_code == 400

    def test_empty_required_parameter(self):
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '', 'start': '1000000'}
        )
        assert response.status_code == 400
```

### Authentication Tests

```python
# tests/security/test_authentication.py
import pytest
from django.test import TestCase


class TestJWTAuthentication(TestCase):
    def test_missing_token_returns_401(self):
        response = self.client.get('/api/g_variants')
        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        response = self.client.get(
            '/api/g_variants',
            HTTP_AUTHORIZATION='Bearer invalid_token_here'
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self):
        expired_token = self.generate_expired_jwt()
        response = self.client.get(
            '/api/g_variants',
            HTTP_AUTHORIZATION=f'Bearer {expired_token}'
        )
        assert response.status_code == 401

    def test_valid_token_allows_access(self):
        valid_token = self.generate_valid_jwt()
        response = self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'},
            HTTP_AUTHORIZATION=f'Bearer {valid_token}'
        )
        assert response.status_code == 200
```

### CORS and Security Headers Tests

```python
# tests/security/test_security_headers.py
import pytest
from django.test import TestCase


class TestSecurityHeaders(TestCase):
    def test_cors_headers_present(self):
        response = self.client.options('/api/g_variants')
        assert 'Access-Control-Allow-Origin' in response

    def test_content_security_policy(self):
        response = self.client.get('/api/')
        assert 'Content-Security-Policy' in response

    def test_xframe_options(self):
        response = self.client.get('/api/')
        assert 'X-Frame-Options' in response
        assert response['X-Frame-Options'] == 'DENY'

    def test_xss_protection(self):
        response = self.client.get('/api/')
        assert 'X-Content-Type-Options' in response
        assert response['X-Content-Type-Options'] == 'nosniff'
```

## Performance Testing

Performance tests ensure the API meets response time and throughput targets.

### Query Performance Tests

```python
# tests/performance/test_query_performance.py
import pytest
import time
from django.test import TestCase


class TestQueryPerformance(TestCase):
    def setUp(self):
        # Load 1000+ test variants
        self.load_large_dataset()

    @pytest.mark.performance
    def test_simple_query_response_time(self):
        """Simple queries should respond in <100ms"""
        start = time.time()
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '1',
                'start': '1000000',
                'referenceBases': 'A',
                'alternateBases': 'T'
            }
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.1  # 100ms target

    @pytest.mark.performance
    def test_range_query_response_time(self):
        """Range queries should respond in <200ms"""
        start = time.time()
        response = self.client.get(
            '/api/g_variants',
            {
                'assemblyId': 'GRCh38',
                'referenceName': '1',
                'start': '1000000',
                'end': '2000000'
            }
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.2  # 200ms target for range queries

    @pytest.mark.performance
    def test_cache_improves_performance(self):
        """Cached queries should be significantly faster"""
        # First query - cache miss
        start1 = time.time()
        self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
        )
        duration1 = time.time() - start1

        # Second query - cache hit
        start2 = time.time()
        self.client.get(
            '/api/g_variants',
            {'assemblyId': 'GRCh38', 'referenceName': '1', 'start': '1000000'}
        )
        duration2 = time.time() - start2

        # Cached query should be at least 2x faster
        assert duration2 < duration1 / 2
```

### Load Testing with Locust

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between


class BeaconUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def query_variant_simple(self):
        """Most common query type"""
        self.client.get(
            "/api/g_variants",
            params={
                "assemblyId": "GRCh38",
                "referenceName": "1",
                "start": "1000000",
                "referenceBases": "A",
                "alternateBases": "T"
            }
        )

    @task(2)
    def query_variant_range(self):
        """Range queries"""
        self.client.get(
            "/api/g_variants",
            params={
                "assemblyId": "GRCh38",
                "referenceName": "17",
                "start": "7000000",
                "end": "8000000"
            }
        )

    @task(1)
    def query_individuals(self):
        """Individual queries"""
        self.client.get(
            "/api/individuals",
            params={"filters": "NCIT:C16576"}
        )

    @task(1)
    def query_biosamples(self):
        """Biosample queries"""
        self.client.get(
            "/api/biosamples",
            params={"filters": "UBERON:0000178"}
        )

    def on_start(self):
        """Called when a user starts"""
        # Could authenticate here for secure mode testing
        pass


class AuthenticatedBeaconUser(HttpUser):
    """For testing secure mode with authentication"""
    wait_time = between(1, 2)

    def on_start(self):
        # Obtain JWT token
        response = self.client.post(
            "/auth/token",
            json={"username": "testuser", "password": "testpass"}
        )
        self.token = response.json()["token"]

    @task
    def query_with_full_records(self):
        self.client.get(
            "/api/g_variants",
            params={
                "assemblyId": "GRCh38",
                "referenceName": "1",
                "start": "1000000",
                "requestedGranularity": "record"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

**Running Load Tests**:
```bash
# Start load test
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Open browser to http://localhost:8089
# Configure:
# - Number of users: 100
# - Spawn rate: 10 users/second
# - Host: http://localhost:8000

# Run headless (CI/CD)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --html=reports/locust_report.html
```

## Test Data Management

### Sample Data Fixtures

Create reusable test fixtures:

```python
# tests/fixtures/factory.py
import factory
from faker import Faker
from beacon_api.models import GenomicVariant, Individual, Biosample

fake = Faker()


class GenomicVariantFactory(factory.Factory):
    class Meta:
        model = GenomicVariant

    id = factory.Sequence(lambda n: f"var-{n:06d}")
    assembly_id = "GRCh38"
    reference_name = factory.Iterator(["1", "2", "3", "X", "Y"])
    start = factory.Faker('random_int', min=1, max=200000000)
    reference_bases = factory.Iterator(["A", "T", "C", "G"])
    alternate_bases = factory.Iterator(["A", "T", "C", "G", "-"])


class IndividualFactory(factory.Factory):
    class Meta:
        model = Individual

    id = factory.Sequence(lambda n: f"ind-{n:06d}")
    sex = factory.Iterator(["male", "female"])
    ethnicity = factory.Iterator(["NCIT:C16352", "NCIT:C41261"])


class BiosampleFactory(factory.Factory):
    class Meta:
        model = Biosample

    id = factory.Sequence(lambda n: f"bio-{n:06d}")
    individual_id = factory.LazyFunction(lambda: IndividualFactory().id)
    biosample_type = factory.Iterator(["UBERON:0000178", "UBERON:0001013"])
```

### Test Data Loading

```bash
# scripts/load_test_data.sh
#!/bin/bash

echo "Loading test data..."

# Load genomic variants
docker exec beacon-mongodb mongoimport --jsonArray \
  --uri "mongodb://localhost:27017/beacon_test" \
  --file /data/test_variants.json \
  --collection genomicVariations \
  --drop

# Load individuals
docker exec beacon-mongodb mongoimport --jsonArray \
  --uri "mongodb://localhost:27017/beacon_test" \
  --file /data/test_individuals.json \
  --collection individuals \
  --drop

# Load biosamples
docker exec beacon-mongodb mongoimport --jsonArray \
  --uri "mongodb://localhost:27017/beacon_test" \
  --file /data/test_biosamples.json \
  --collection biosamples \
  --drop

# Create indexes
docker exec beacon-api python manage.py create_indexes

echo "Test data loaded successfully"
```

### CINECA Synthetic Dataset

The [EGA Beacon v2 Training Environment](https://github.com/EGA-archive/beacon-2.x-training-ui) uses the **CINECA Synthetic Dataset** (EGAD00001003338):

- **2504 samples** from 1000 Genomes Project
- **UK Biobank synthetic phenotypes**
- Comprehensive coverage for testing queries

**Accessing the dataset**:
1. Register at [EGA Archive](https://ega-archive.org/)
2. Request access to EGAD00001003338
3. Download VCF and phenotype files
4. Transform to Beacon format using data tools

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    services:
      mongodb:
        image: mongo:5.0
        ports:
          - 27017:27017
        options: >-
          --health-cmd "mongosh --eval 'db.adminCommand({ping: 1})'"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:6
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Load test data
        run: |
          python scripts/load_test_data.py

      - name: Run linting
        run: |
          pip install flake8 black isort
          flake8 beacon_api --max-line-length=100
          black --check beacon_api
          isort --check-only beacon_api

      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --tb=short

      - name: Run integration tests
        run: |
          pytest tests/integration/ -v --tb=short

      - name: Run security tests
        run: |
          pytest tests/security/ -v --tb=short

      - name: Run performance tests
        run: |
          pytest tests/performance/ -v -m performance --tb=short

      - name: Run tests with coverage
        run: |
          pytest --cov=beacon_api \
                 --cov-report=xml \
                 --cov-report=term \
                 --cov-report=html

      - name: Check coverage threshold
        run: |
          coverage report --fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-${{ matrix.python-version }}

      - name: Upload coverage reports
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report-${{ matrix.python-version }}
          path: htmlcov/

      - name: Security scan with Bandit
        run: |
          pip install bandit
          bandit -r beacon_api -f json -o bandit-report.json

      - name: Upload security report
        uses: actions/upload-artifact@v3
        with:
          name: security-report
          path: bandit-report.json

  load-test:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Start Beacon API
        run: |
          docker-compose -f docker-compose-boolean.yml up -d
          sleep 30  # Wait for services to be ready

      - name: Run load tests
        run: |
          pip install locust
          locust -f tests/performance/locustfile.py \
            --host=http://localhost:8000 \
            --users 50 \
            --spawn-rate 5 \
            --run-time 2m \
            --headless \
            --html=reports/locust_report.html

      - name: Upload load test report
        uses: actions/upload-artifact@v3
        with:
          name: load-test-report
          path: reports/locust_report.html
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']

  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest-unit
        entry: pytest tests/unit/ -v
        language: system
        pass_filenames: false
        always_run: true
```

**Install pre-commit**:
```bash
pip install pre-commit
pre-commit install
```

## Coverage & Quality Metrics

### Coverage Targets

| Component | Minimum | Target | Current |
|-----------|---------|--------|---------|
| Overall | 80% | 100% | TBD |
| Models | 90% | 100% | TBD |
| Views | 85% | 100% | TBD |
| Validators | 95% | 100% | TBD |
| Serializers | 85% | 95% | TBD |

### Generating Coverage Reports

```bash
# Run tests with coverage
pytest --cov=beacon_api --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Generate XML report (for CI/CD)
pytest --cov=beacon_api --cov-report=xml

# Check coverage threshold
coverage report --fail-under=80

# View missing coverage
coverage report --show-missing
```

### Quality Gates

Tests must pass these gates before merging:

1. **All tests pass**: No failures in any test suite
2. **Coverage ≥80%**: Minimum code coverage threshold
3. **No critical security issues**: Bandit scan passes
4. **Performance benchmarks met**: <100ms response time
5. **Linting passes**: flake8, black, isort all pass

## Troubleshooting

### Common Issues

#### MongoDB Connection Errors

**Problem**: `pymongo.errors.ServerSelectionTimeoutError`

**Solutions**:
```bash
# Check MongoDB is running
docker ps | grep mongodb

# Check connection string
echo $MONGODB_HOST

# Test connection manually
docker exec beacon-mongodb mongosh beacon_test --eval "db.stats()"

# Restart MongoDB
docker-compose restart mongodb
```

#### Redis Connection Errors

**Problem**: `redis.exceptions.ConnectionError`

**Solutions**:
```bash
# Check Redis is running
docker ps | grep redis

# Test Redis connection
docker exec beacon-redis redis-cli ping

# Clear Redis cache
docker exec beacon-redis redis-cli FLUSHDB

# Restart Redis
docker-compose restart redis
```

#### Test Isolation Problems

**Problem**: Tests pass individually but fail when run together

**Solutions**:
```python
# Ensure proper cleanup in fixtures
@pytest.fixture
def mongo_db():
    disconnect()
    connect('beacon_test', host='mongomock://localhost')
    yield
    disconnect()  # Clean up after test

# Clear cache between tests
@pytest.fixture(autouse=True)
def clear_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

#### Slow Test Execution

**Problem**: Test suite takes too long

**Solutions**:
```bash
# Run tests in parallel
pytest -n auto

# Run only fast tests
pytest -m "not slow"

# Profile slow tests
pytest --durations=10

# Use in-memory database
# In settings_test.py:
MONGODB_HOST = 'mongomock://localhost'
```

#### Flaky Tests

**Problem**: Tests pass/fail randomly

**Solutions**:
- Use `freezegun` to control time-based tests
- Mock external API calls with `responses`
- Ensure proper test isolation
- Increase timeouts for async operations
- Use deterministic test data (avoid random values)

### Debug Mode

Enable verbose test output:

```bash
# Verbose output
pytest -v

# Very verbose output
pytest -vv

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Show local variables in tracebacks
pytest -l

# Show longest running tests
pytest --durations=20
```

## Resources

### Official Documentation
- [GA4GH Beacon v2 Specification](https://docs.genomebeacons.org/)
- [Beacon v2 REST API](https://docs.genomebeacons.org/rest-api/)
- [Genomic Variant Queries](https://docs.genomebeacons.org/variant-queries/)
- [B2RI Documentation](https://b2ri-documentation.readthedocs.io/)

### Reference Implementations
- [EGA Beacon v2 RI API](https://github.com/EGA-archive/beacon2-ri-api) - Reference Implementation
- [EGA Beacon v2 PI API](https://github.com/EGA-archive/beacon2-pi-api) - Production Instance (313 tests)
- [Beacon v2 Training UI](https://github.com/EGA-archive/beacon-2.x-training-ui) - Training environment

### Testing Frameworks
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-django](https://pytest-django.readthedocs.io/)
- [Locust Documentation](https://docs.locust.io/)
- [Factory Boy](https://factoryboy.readthedocs.io/)

### Test Data
- [CINECA Synthetic Dataset](https://ega-archive.org/) - EGAD00001003338
- [1000 Genomes Project](https://www.internationalgenome.org/)

---

**Note**: This testing documentation is based on best practices from the EGA Beacon v2 Reference Implementation and Public Instance, which maintain production-grade test coverage and performance benchmarks.
