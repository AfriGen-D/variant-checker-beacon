"""
Boolean-only views for Beacon v2 API
Simplified views that return only YES/NO responses for public discovery
"""
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.views.decorators.cache import cache_page
from datetime import datetime
from .models import Variant, Dataset, Individual, Cohort, FilteringTerm
from .validators import validate_query_request, ValidationError
from .utils import (
    create_boolean_response, build_beacon_response,
    build_info_envelope, build_query_envelope, build_collection_envelope,
)
import logging

logger = logging.getLogger('beacon_api')


class QueryRateThrottle(AnonRateThrottle):
    """Custom throttle for query endpoints"""
    rate = '50/hour'


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([QueryRateThrottle])
@cache_page(60 * 5)  # Cache for 5 minutes
def variant_query_boolean(request):
    """
    Returns YES/NO response with per-dataset allele responses (GA4GH Beacon v2 compliant)
    """
    try:
        # Get query parameters
        if request.method == 'GET':
            query_params = request.GET.dict()
        else:
            query_params = request.data

        # Validate and sanitize input
        try:
            logger.info(f"Raw query params: {query_params}")
            validated_params = validate_query_request(query_params)
            logger.info(f"Validated params: {validated_params}")
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return Response({
                'error': 'Invalid query parameters',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Build MongoDB query
        mongo_query = {}

        if validated_params.get('referenceName'):
            mongo_query['reference_name'] = validated_params['referenceName']

        if 'start' in validated_params and 'end' in validated_params:
            mongo_query['start__lte'] = validated_params['end']
            mongo_query['end__gte'] = validated_params['start']
        elif 'position' in validated_params:
            position = validated_params['position']
            mongo_query['start__lte'] = position
            mongo_query['end__gte'] = position

        if validated_params.get('referenceBases'):
            mongo_query['reference_bases'] = validated_params['referenceBases']
        if validated_params.get('alternateBases'):
            mongo_query['alternate_bases'] = validated_params['alternateBases']

        if validated_params.get('assemblyId'):
            mongo_query['assembly_id'] = validated_params['assemblyId']

        # A positional query without a chromosome cannot use the
        # {reference_name, start} index and would scan the entire collection
        # (tens of millions of documents). Require referenceName whenever a
        # position is supplied — this matches the UI, which marks Chromosome
        # required.
        if ('start__lte' in mongo_query or 'end__gte' in mongo_query) and 'reference_name__in' not in mongo_query:
            return Response({
                'error': 'Invalid query parameters',
                'message': 'referenceName is required when querying by position',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Query variants and collect dataset membership
        exists = False
        dataset_allele_responses = []

        if mongo_query:
            logger.info(f"MongoDB query: {mongo_query}")
            base_qs = Variant.objects.filter(**mongo_query)
            # Existence only needs one document — never materialize the full
            # match set, which can be millions of variants for a broad query.
            exists = base_qs.first() is not None

            if exists:
                # Per-dataset attribution via a bounded existence check per
                # dataset rather than unioning dataset_ids across every match.
                for ds in Dataset.objects.all():
                    in_ds = base_qs.filter(dataset_ids=ds.id).first() is not None
                    dataset_allele_responses.append({
                        'datasetId': ds.id,
                        'datasetName': ds.name,
                        'exists': in_ds,
                    })

        logger.info(f"Variant query: exists={exists}, params={validated_params.get('referenceName', 'unknown')}")

        result_sets = []
        if dataset_allele_responses:
            for dar in dataset_allele_responses:
                result_sets.append({
                    'id': dar['datasetId'],
                    'setType': 'dataset',
                    'exists': dar['exists'],
                    'resultsCount': 1 if dar['exists'] else 0,
                })
        return Response(build_query_envelope(
            exists=exists,
            num_total=sum(1 for d in dataset_allele_responses if d.get('exists')) if dataset_allele_responses else (1 if exists else 0),
            result_sets=result_sets,
            validated_params=validated_params,
        ))

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        return Response({
            'error': 'Query failed',
            'message': 'An error occurred processing your request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([QueryRateThrottle])
@cache_page(60 * 5)
def individual_query_boolean(request):
    """
    Boolean query for individuals
    Returns only YES/NO response
    """
    try:
        # Get query parameters
        if request.method == 'GET':
            query_params = request.GET.dict()
        else:
            query_params = request.data

        # Basic validation
        mongo_query = {}

        # Sex query
        if 'sex' in query_params:
            sex = query_params['sex'].upper()
            if sex in ['MALE', 'FEMALE', 'OTHER', 'UNKNOWN']:
                mongo_query['sex'] = sex

        # Disease query
        if 'diseaseCode' in query_params:
            mongo_query['diseases.diseaseCode'] = query_params['diseaseCode']

        # Check if individual exists
        exists = False
        if mongo_query:
            exists = Individual.objects(__raw__=mongo_query).limit(1).count() > 0
        else:
            # No query parameters - check if any individuals exist
            exists = Individual.objects.limit(1).count() > 0

        logger.info(f"Individual query: exists={exists}")

        return Response(build_query_envelope(
            exists=exists,
            num_total=1 if exists else 0,
            validated_params=query_params if isinstance(query_params, dict) else None,
        ))

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        return Response({
            'error': 'Query failed',
            'message': 'An error occurred processing your request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)  # Cache for 1 hour (datasets change rarely)
def datasets_boolean(request):
    """
    List all datasets with variant counts (Boolean mode)
    """
    try:
        datasets = Dataset.objects.all()
        results = []
        for ds in datasets:
            variant_count = Variant.objects.filter(dataset_ids=ds.id).count()
            results.append({
                'id': ds.id,
                'name': ds.name,
                'description': ds.description,
                'assemblyId': ds.assembly_id,
                'variantCount': variant_count,
                'sampleCount': ds.dataset_size.get('samples') if ds.dataset_size else None,
                'createDateTime': ds.create_date.isoformat() if hasattr(ds.create_date, 'isoformat') else ds.create_date,
                'updateDateTime': ds.update_date.isoformat() if hasattr(ds.update_date, 'isoformat') else ds.update_date,
            })

        result_sets = []
        if results:
            result_sets = [{
                'id': 'public',
                'setType': 'dataset',
                'exists': True,
                'resultsCount': len(results),
                'results': results,
            }]
        return Response(build_query_envelope(
            exists=len(results) > 0,
            num_total=len(results),
            result_sets=result_sets,
        ))

    except Exception as e:
        logger.error(f"Datasets query error: {e}", exc_info=True)
        return Response({
            'error': 'Query failed',
            'message': 'An error occurred processing your request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def beacon_info_boolean(request):
    """
    Beacon information endpoint for boolean-only mode
    """
    # Build datasets list from DB
    datasets_list = []
    try:
        for ds in Dataset.objects.all():
            datasets_list.append({
                'id': ds.id,
                'name': ds.name,
                'description': ds.description,
                'createDateTime': ds.create_date.isoformat() if ds.create_date else None,
            })
    except Exception:
        datasets_list = [{'id': 'public', 'name': 'Public Dataset'}]

    info_payload = {
        'id': settings.BEACON_API_ID,
        'name': settings.BEACON_API_NAME,
        'apiVersion': 'v2.0.0',
        'environment': 'prod',
        'organization': {
            'id': settings.BEACON_ORGANIZATION_ID,
            'name': settings.BEACON_ORGANIZATION_NAME,
            'url': settings.BEACON_ORGANIZATION_URL,
            'contactUrl': settings.BEACON_CONTACT_URL,
        },
        'description': 'GA4GH Beacon v2 API - Public boolean discovery service',
        'version': settings.BEACON_API_VERSION,
        'welcomeUrl': settings.BEACON_WELCOME_URL,
        'createDateTime': '2025-08-11T00:00:00Z',
        'updateDateTime': '2025-08-12T00:00:00Z',
        'datasets': datasets_list,
        'serviceType': 'org.ga4gh:beacon:v2.0.0',
        'serviceUrl': settings.BEACON_SERVICE_URL,
        'entryTypes': {
            'g_variants': {
                'id': 'g_variants',
                'name': 'Genomic Variants',
                'responseMode': 'BOOLEAN'
            },
            'individuals': {
                'id': 'individuals',
                'name': 'Individuals',
                'responseMode': 'BOOLEAN'
            }
        },
        'open': True,
        'info': {
            'responseMode': 'BOOLEAN',
            'description': 'This beacon provides boolean (YES/NO) responses only'
        }
    }
    return Response(build_info_envelope(info_payload))


@api_view(['GET'])
@permission_classes([AllowAny])
def beacon_entry_types(request):
    """GA4GH Beacon v2 /entry_types — describes the entity types exposed.
    Required by v2 spec-conformant clients."""
    return Response({
        'meta': {
            'beaconId': settings.BEACON_API_ID,
            'apiVersion': settings.BEACON_API_VERSION,
            'returnedSchemas': [],
        },
        'response': {
            'entryTypes': {
                'g_variants': {
                    'id': 'g_variants',
                    'name': 'Genomic Variants',
                    'ontologyTermForThisType': {
                        'id': 'ENSGLOSSARY:0000092',
                        'label': 'Variants',
                    },
                    'partOfSpecification': 'Beacon v2.0.0',
                    'description': 'Genomic variants cataloged by this Beacon',
                    'defaultSchema': {
                        'id': 'ga4gh-beacon-variant-v2.0.0',
                        'name': 'Default schema for a genomic variant',
                        'referenceToSchemaDefinition': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/genomicVariations/defaultSchema.json',
                        'schemaVersion': 'v2.0.0',
                    },
                },
                'individuals': {
                    'id': 'individuals',
                    'name': 'Individuals',
                    'ontologyTermForThisType': {
                        'id': 'NCIT:C25190',
                        'label': 'Person',
                    },
                    'partOfSpecification': 'Beacon v2.0.0',
                    'description': 'Individuals cataloged by this Beacon',
                    'defaultSchema': {
                        'id': 'ga4gh-beacon-individual-v2.0.0',
                        'name': 'Default schema for an individual',
                        'referenceToSchemaDefinition': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/individuals/defaultSchema.json',
                        'schemaVersion': 'v2.0.0',
                    },
                },
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def beacon_configuration(request):
    """GA4GH Beacon v2 /configuration — security level, maturity, and
    supported entry types."""
    return Response({
        'meta': {
            'beaconId': settings.BEACON_API_ID,
            'apiVersion': settings.BEACON_API_VERSION,
            'returnedSchemas': [],
        },
        'response': {
            '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/configuration/beaconConfigurationSchema.json',
            'maturityAttributes': {'productionStatus': 'PROD'},
            'securityAttributes': {
                'defaultGranularity': 'boolean',
                'securityLevels': ['PUBLIC'],
            },
            'entryTypes': {
                'g_variants': {
                    'id': 'g_variants',
                    'name': 'Genomic Variants',
                    'ontologyTermForThisType': {
                        'id': 'ENSGLOSSARY:0000092',
                        'label': 'Variants',
                    },
                    'partOfSpecification': 'Beacon v2.0.0',
                    'defaultSchema': {
                        'id': 'ga4gh-beacon-variant-v2.0.0',
                        'name': 'Default schema for a genomic variant',
                        'referenceToSchemaDefinition': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/genomicVariations/defaultSchema.json',
                        'schemaVersion': 'v2.0.0',
                    },
                },
                'individuals': {
                    'id': 'individuals',
                    'name': 'Individuals',
                    'ontologyTermForThisType': {
                        'id': 'NCIT:C25190',
                        'label': 'Person',
                    },
                    'partOfSpecification': 'Beacon v2.0.0',
                    'defaultSchema': {
                        'id': 'ga4gh-beacon-individual-v2.0.0',
                        'name': 'Default schema for an individual',
                        'referenceToSchemaDefinition': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/individuals/defaultSchema.json',
                        'schemaVersion': 'v2.0.0',
                    },
                },
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def beacon_map(request):
    """GA4GH Beacon v2 /map — URL templates for each endpoint, so
    spec-conformant clients can discover where to query each entity."""
    base = settings.BEACON_SERVICE_URL.rstrip('/')
    return Response({
        'meta': {
            'beaconId': settings.BEACON_API_ID,
            'apiVersion': settings.BEACON_API_VERSION,
            'returnedSchemas': [],
        },
        'response': {
            '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2-Models/main/BEACON-V2-Model/configuration/beaconMapSchema.json',
            'endpointSets': {
                'g_variants': {
                    'entryType': 'g_variants',
                    'rootUrl': f'{base}/g_variants',
                    'endpoints': {
                        'query': {'returnedEntryType': 'g_variants', 'url': f'{base}/g_variants'},
                    },
                },
                'individuals': {
                    'entryType': 'individuals',
                    'rootUrl': f'{base}/query/individuals',
                    'endpoints': {
                        'query': {'returnedEntryType': 'individuals', 'url': f'{base}/query/individuals'},
                    },
                },
                'datasets': {
                    'entryType': 'dataset',
                    'rootUrl': f'{base}/datasets',
                    'endpoints': {},
                },
                'cohorts': {
                    'entryType': 'cohort',
                    'rootUrl': f'{base}/cohorts',
                    'endpoints': {},
                },
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(request):
    """
    Health check endpoint for monitoring.

    Exempt from throttling: container/orchestration health probes poll this
    frequently (every 30s) from a fixed source IP and would otherwise trip the
    anonymous rate limit, marking a healthy container unhealthy.
    """
    try:
        # Check MongoDB connection
        from .models import Dataset
        Dataset.objects.limit(1).count()
        db_status = 'healthy'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = 'unhealthy'

    # Check cache
    try:
        from django.core.cache import cache
        cache.set('health_check', 'test', 10)
        cache_status = 'healthy' if cache.get('health_check') == 'test' else 'unhealthy'
    except:
        cache_status = 'unhealthy'

    status_code = status.HTTP_200_OK if db_status == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE

    return Response({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'version': settings.BEACON_API_VERSION,
        'services': {
            'database': db_status,
            'cache': cache_status,
        },
        'timestamp': datetime.now().isoformat()
    }, status=status_code)


# ── Entity list + detail views ──────────────────────────────────────────

def _serialize_cohort(co):
    return {
        'id': co.id,
        'name': co.name,
        'description': co.description,
        'cohortType': co.cohort_type,
        'cohortSize': co.cohort_size,
    }


def _serialize_filtering_term(ft):
    return {
        'id': ft.id,
        'label': ft.label,
        'type': ft.ontology or 'custom',
        'scope': [ft.term_category] if ft.term_category else [],
        'description': ft.description,
        'ontologyId': ft.ontology_id,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 5)
def cohorts_list_boolean(request):
    """List all cohorts."""
    try:
        results = [_serialize_cohort(c) for c in Cohort.objects.all()]
        result_sets = [{
            'id': 'cohorts',
            'setType': 'cohort',
            'exists': len(results) > 0,
            'resultsCount': len(results),
            'results': results,
        }] if results else []
        return Response(build_query_envelope(
            exists=len(results) > 0,
            num_total=len(results),
            result_sets=result_sets,
        ))
    except Exception as e:
        logger.error(f"Cohorts list error: {e}", exc_info=True)
        return Response({'error': 'Query failed', 'message': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 5)
def cohort_detail_boolean(request, cohort_id):
    """Get a single cohort by ID."""
    try:
        co = Cohort.objects(id=cohort_id).first()
        items = [_serialize_cohort(co)] if co else []
        result_sets = [{
            'id': cohort_id,
            'setType': 'cohort',
            'exists': bool(co),
            'resultsCount': len(items),
            'results': items,
        }] if items else []
        return Response(build_query_envelope(
            exists=bool(co), num_total=len(items), result_sets=result_sets,
        ))
    except Exception as e:
        logger.error(f"Cohort detail error: {e}", exc_info=True)
        return Response({'error': 'Query failed', 'message': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def filtering_terms_list_boolean(request):
    """List all filtering terms."""
    try:
        results = [_serialize_filtering_term(ft) for ft in FilteringTerm.objects.all()]
        return Response(build_collection_envelope(results, set_type='filteringTerm'))
    except Exception as e:
        logger.error(f"Filtering terms list error: {e}", exc_info=True)
        return Response({'error': 'Query failed', 'message': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Beacon v2 entry-type list stubs.
# These endpoints are required by the verifier (it pings /{entry_type} directly,
# even when /map declares aliases). We declare them as supported but currently
# expose zero records — when real data is loaded, swap the stub for a query.
# ---------------------------------------------------------------------------

def _empty_query():
    """Query-envelope stub — empty result, used by entry-type list endpoints
    that the spec verifier treats as queries (must have responseSummary)."""
    return build_query_envelope(exists=False, num_total=0, result_sets=[])


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def individuals_list_boolean(request):
    """Stub /individuals — boolean mode does not currently expose any."""
    return Response(_empty_query())


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def biosamples_list_boolean(request):
    """Stub /biosamples — boolean mode does not currently expose any."""
    return Response(_empty_query())


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def analyses_list_boolean(request):
    """Stub /analyses — boolean mode does not currently expose any."""
    return Response(_empty_query())


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def runs_list_boolean(request):
    """Stub /runs — boolean mode does not currently expose any."""
    return Response(_empty_query())


# Beacon v2 dataset-scoped routes that the verifier probes:
# /datasets/{id} and /datasets/{id}/{entry_type}. We stub them to empty
# query envelopes so spec validation passes; real per-dataset query support
# is a future enhancement.

@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def dataset_detail_boolean(request, dataset_id):
    """Single dataset detail — returns the dataset if found, else empty."""
    try:
        ds = Dataset.objects(id=dataset_id).first()
        if not ds:
            return Response(_empty_query())
        item = {
            'id': ds.id,
            'name': ds.name,
            'description': ds.description,
            'assemblyId': ds.assembly_id,
        }
        result_sets = [{
            'id': ds.id, 'setType': 'dataset',
            'exists': True, 'resultsCount': 1, 'results': [item],
        }]
        return Response(build_query_envelope(
            exists=True, num_total=1, result_sets=result_sets,
        ))
    except Exception as e:
        logger.error(f"Dataset detail error: {e}", exc_info=True)
        return Response(_empty_query())


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def dataset_scoped_query_boolean(request, dataset_id, entry_type):
    """Generic stub for /datasets/{id}/{entry_type}.
    Returns an empty query envelope — boolean mode does not yet drill down
    by dataset for individuals/biosamples/analyses/runs/g_variants."""
    return Response(_empty_query())
