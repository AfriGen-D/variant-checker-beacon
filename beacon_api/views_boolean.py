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
from .utils import create_boolean_response, build_beacon_response
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
    Boolean query for genomic variants
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

        # Query variants and collect dataset membership
        exists = False
        dataset_allele_responses = []

        if mongo_query:
            logger.info(f"MongoDB query: {mongo_query}")
            matched_variants = list(Variant.objects.filter(**mongo_query).only('dataset_ids'))
            exists = len(matched_variants) > 0

            if exists:
                # Collect dataset_ids from matched variants
                matched_dataset_ids = set()
                for v in matched_variants:
                    matched_dataset_ids.update(v.dataset_ids or [])

                # Get all datasets to build per-dataset responses
                all_datasets = Dataset.objects.all()
                for ds in all_datasets:
                    dataset_allele_responses.append({
                        'datasetId': ds.id,
                        'datasetName': ds.name,
                        'exists': ds.id in matched_dataset_ids,
                    })

        logger.info(f"Variant query: exists={exists}, params={validated_params.get('referenceName', 'unknown')}")

        return Response(create_boolean_response(
            exists,
            dataset_allele_responses=dataset_allele_responses if dataset_allele_responses else None,
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

        return Response(create_boolean_response(exists))

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
                'createDateTime': ds.create_date.isoformat() if ds.create_date else None,
                'updateDateTime': ds.update_date.isoformat() if ds.update_date else None,
            })

        return Response({
            'apiVersion': 'v2.0.0',
            'beaconId': settings.BEACON_API_ID,
            'datasets': results,
        })

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

    return Response({
        'id': settings.BEACON_API_ID,
        'name': settings.BEACON_API_NAME,
        'apiVersion': 'v2.0.0',
        'organization': {
            'id': settings.BEACON_ORGANIZATION_ID,
            'name': settings.BEACON_ORGANIZATION_NAME,
        },
        'description': 'GA4GH Beacon v2 API - Public boolean discovery service',
        'version': settings.BEACON_API_VERSION,
        'welcomeUrl': 'https://beacon.afrigend.org',
        'createDateTime': '2025-08-11T00:00:00Z',
        'updateDateTime': '2025-08-12T00:00:00Z',
        'datasets': datasets_list,
        'serviceType': 'org.ga4gh:beacon:v2.0.0',
        'serviceUrl': 'https://beacon.afrigend.org/api/',
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
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring
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
        return Response(build_beacon_response(results))
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
        if not co:
            return Response(build_beacon_response([]), status=status.HTTP_200_OK)
        return Response(build_beacon_response([_serialize_cohort(co)], num_total=1))
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
        return Response(build_beacon_response(results))
    except Exception as e:
        logger.error(f"Filtering terms list error: {e}", exc_info=True)
        return Response({'error': 'Query failed', 'message': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
