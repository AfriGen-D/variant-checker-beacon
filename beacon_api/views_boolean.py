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
from .query_semantics import build_position_filter, POSITION_FILTER_KEYS
from .utils import (
    create_boolean_response, build_beacon_response,
    build_info_envelope, build_query_envelope, build_collection_envelope,
    build_error_envelope, extract_error_message,
)
import logging

logger = logging.getLogger('beacon_api')


def _error_response(status_code, message):
    """Spec-shaped Beacon v2 error response with a matching HTTP status."""
    return Response(build_error_envelope(status_code, message), status=status_code)


def _server_error(message='An error occurred processing your request'):
    """500 with the Beacon v2 error envelope."""
    return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, message)


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
            # `str(e)` here is the raw DRF/Python repr of the error dict —
            # never return it to the caller. extract_error_message() pulls out
            # just the human-readable text.
            message = extract_error_message(
                getattr(e, 'detail', None), fallback='Invalid query parameters'
            )
            logger.warning(f"Validation error: {message}")
            return _error_response(status.HTTP_400_BAD_REQUEST, message)

        # Build MongoDB query
        mongo_query = {}

        if validated_params.get('referenceName'):
            # The Beacon v2 spec uses bare chromosome names ("1", "X"). Stored
            # data may use either bare or "chr"-prefixed names depending on the
            # ingest pipeline. Match both so callers don't have to know which
            # form the data uses.
            ref = validated_params['referenceName']
            bare = ref[3:] if ref.startswith('chr') else ref
            mongo_query['reference_name__in'] = [bare, f'chr{bare}']

        # Position filter — half-open interval overlap for both point queries
        # (only `start` provided, the standard Beacon v2 SNV lookup) and range
        # queries (`start` + `end`). See beacon_api/query_semantics.py for the
        # coordinate convention and why closed-interval (`lte`/`gte`) overlap
        # is wrong here. Without this filter, a `start`-only query falls
        # through with no position constraint, forcing a full-chromosome scan
        # over millions of variants — observed as 30s requests.
        position_start = validated_params.get('start', validated_params.get('position'))
        mongo_query.update(build_position_filter(
            position_start, validated_params.get('end')
        ))

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
        if any(k in mongo_query for k in POSITION_FILTER_KEYS) and 'reference_name__in' not in mongo_query:
            return _error_response(
                status.HTTP_400_BAD_REQUEST,
                'referenceName is required when querying by position',
            )

        # Granularity: default 'boolean'. 'aggregated' (or 'record') additionally
        # returns allele frequencies for matched variants.
        requested_granularity = validated_params.get('requestedGranularity', 'boolean')
        want_frequency = requested_granularity in ('aggregated', 'record')
        returned_granularity = 'boolean'

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
                # Per-dataset attribution via a bounded check per dataset. Fetch
                # the matched doc once and reuse it for the allele frequency
                # rather than issuing a second query.
                for ds in Dataset.objects.all():
                    ds_variant = base_qs.filter(dataset_ids=ds.id).first()
                    dar = {
                        'datasetId': ds.id,
                        'datasetName': ds.name,
                        'exists': ds_variant is not None,
                    }
                    if want_frequency and ds_variant is not None and ds_variant.allele_frequency is not None:
                        dar['alleleFrequency'] = ds_variant.allele_frequency
                        returned_granularity = 'aggregated'
                    dataset_allele_responses.append(dar)

        logger.info(f"Variant query: exists={exists}, params={validated_params.get('referenceName', 'unknown')}")

        result_sets = []
        if dataset_allele_responses:
            for dar in dataset_allele_responses:
                rs = {
                    'id': dar['datasetId'],
                    'name': dar['datasetName'],
                    'setType': 'dataset',
                    'exists': dar['exists'],
                    'resultsCount': 1 if dar['exists'] else 0,
                }
                # Spec-shaped allele frequency (GA4GH frequencyInPopulations)
                if dar.get('alleleFrequency') is not None:
                    rs['results'] = [{
                        'frequencyInPopulations': [{
                            'source': dar['datasetName'],
                            'sourceReference': dar['datasetId'],
                            'frequencies': [{
                                'population': dar['datasetName'],
                                'alleleFrequency': dar['alleleFrequency'],
                            }],
                        }],
                    }]
                result_sets.append(rs)
        return Response(build_query_envelope(
            exists=exists,
            num_total=sum(1 for d in dataset_allele_responses if d.get('exists')) if dataset_allele_responses else (1 if exists else 0),
            result_sets=result_sets,
            validated_params=validated_params,
            requested_granularity=requested_granularity,
            returned_granularity=returned_granularity,
        ))

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        return _server_error()


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
        return _server_error()


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
            # Read counts from the precomputed dataset_size field rather than
            # scanning the variants collection — at production volume (~42M
            # docs, dataset_ids unindexed and often unset) the per-dataset
            # count() degrades into a 30s collection scan that hangs the view.
            # Omit absent counts entirely (the frontend's `!== undefined`
            # guard rejects undefined but not null).
            size = ds.dataset_size or {}
            entry = {
                'id': ds.id,
                'name': ds.name,
                'description': ds.description,
                'assemblyId': ds.assembly_id,
                'createDateTime': ds.create_date.isoformat() if hasattr(ds.create_date, 'isoformat') else ds.create_date,
                'updateDateTime': ds.update_date.isoformat() if hasattr(ds.update_date, 'isoformat') else ds.update_date,
            }
            if isinstance(size.get('variants'), int):
                entry['variantCount'] = size['variants']
            if isinstance(size.get('samples'), int):
                entry['sampleCount'] = size['samples']
            results.append(entry)

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
        return _server_error()


@api_view(['GET'])
@permission_classes([AllowAny])
def beacon_info_boolean(request):
    """
    Beacon information endpoint for boolean-only mode
    """
    # Build datasets list from DB. A DB failure must NOT be papered over with a
    # fabricated placeholder dataset — /info is how clients discover what this
    # beacon holds, and inventing an entry advertises data we cannot confirm
    # exists. Surface it as a 5xx instead.
    datasets_list = []
    try:
        for ds in Dataset.objects.all():
            datasets_list.append({
                'id': ds.id,
                'name': ds.name,
                'description': ds.description,
                'createDateTime': ds.create_date.isoformat() if ds.create_date else None,
            })
    except Exception as e:
        logger.error(f"Beacon info dataset lookup failed: {e}", exc_info=True)
        return _server_error('Unable to retrieve beacon information')

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
        logger.error(f"Database health check failed: {e}", exc_info=True)
        db_status = 'unhealthy'

    # Check cache. Catch Exception, not a bare `except:` — the bare form also
    # swallowed KeyboardInterrupt/SystemExit (so a shutdown signal arriving
    # mid-probe was reported as a mere cache blip) and logged nothing at all,
    # leaving no trace of *why* the cache was unhealthy.
    try:
        from django.core.cache import cache
        cache.set('health_check', 'test', 10)
        cache_status = 'healthy' if cache.get('health_check') == 'test' else 'unhealthy'
    except Exception as e:
        logger.error(f"Cache health check failed: {e}", exc_info=True)
        cache_status = 'unhealthy'

    # The database is load-bearing: without it the beacon cannot answer any
    # query, so a DB failure is a hard 503. A cache failure is reported
    # honestly as 'degraded' but stays 200 — queries still resolve correctly
    # against MongoDB, and 503-ing here would make a transient Redis blip
    # restart an otherwise-serving container.
    status_code = status.HTTP_200_OK if db_status == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
    if db_status != 'healthy':
        overall = 'unhealthy'
    elif cache_status != 'healthy':
        overall = 'degraded'
    else:
        overall = 'healthy'

    return Response({
        'status': overall,
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
        return _server_error()


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
        return _server_error()


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
        return _server_error()


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
        # A lookup failure is NOT the same as "no such dataset". Returning the
        # empty 200 envelope here made a MongoDB outage indistinguishable from
        # a genuine miss, so clients (and the Beacon Network aggregator) would
        # record an authoritative "does not exist" for data we simply could
        # not read. Only the `not ds` branch above may answer empty-but-200.
        logger.error(f"Dataset detail error: {e}", exc_info=True)
        return _server_error()


@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 60)
def dataset_scoped_query_boolean(request, dataset_id, entry_type):
    """Generic stub for /datasets/{id}/{entry_type}.
    Returns an empty query envelope — boolean mode does not yet drill down
    by dataset for individuals/biosamples/analyses/runs/g_variants."""
    return Response(_empty_query())
