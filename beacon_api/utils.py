"""
Utility functions for Beacon API
"""
import logging
from django.conf import settings
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from .pagination import (
    DEFAULT_LIMIT, DEFAULT_SKIP, InvalidPagination, parse_pagination,
)

logger = logging.getLogger('beacon_api')


def custom_exception_handler(exc, context):
    """
    Custom exception handler that doesn't leak sensitive information
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        # Log the full error for debugging
        logger.error(f"API Error: {exc}", exc_info=True)
        
        # Don't leak stack traces in production
        if not settings.DEBUG:
            if response.status_code == 500:
                response.data = {
                    'error': 'Internal server error',
                    'message': 'An error occurred processing your request'
                }
            elif response.status_code == 400:
                # Keep validation errors but remove sensitive details
                if 'detail' in response.data:
                    response.data = {
                        'error': 'Bad request',
                        'message': str(response.data['detail'])
                    }
    
    return response


def create_boolean_response(exists, query_params=None, dataset_allele_responses=None):
    """
    Create a standardized boolean response for Beacon queries
    """
    response = {
        'exists': exists,
        'apiVersion': 'v2.0.0',
        'beaconId': settings.BEACON_API_ID,
    }

    # In boolean mode, don't include detailed information
    if settings.BEACON_RESPONSE_MODE == 'BOOLEAN':
        response['message'] = 'Query successful'
    else:
        if query_params:
            response['query'] = query_params

    if dataset_allele_responses is not None:
        response['datasetAlleleResponses'] = dataset_allele_responses

    return response


def transform_to_boolean_response(original_response):
    """
    Transform a detailed response to boolean-only response
    """
    if isinstance(original_response, dict):
        # Check if results exist
        exists = False
        
        if 'results' in original_response:
            results = original_response['results']
            if isinstance(results, list) and len(results) > 0:
                exists = True
            elif isinstance(results, dict) and results:
                exists = True
        elif 'data' in original_response:
            data = original_response['data']
            if isinstance(data, list) and len(data) > 0:
                exists = True
        elif 'count' in original_response:
            exists = original_response['count'] > 0
        elif 'exists' in original_response:
            exists = original_response['exists']
        
        return create_boolean_response(exists)
    
    return original_response


def build_beacon_response(results, num_total=None):
    """
    Build a standard GA4GH Beacon v2 response envelope.
    """
    from datetime import datetime
    count = num_total if num_total is not None else len(results)
    return {
        'meta': {
            'apiVersion': 'v2.0.0',
            'beaconId': settings.BEACON_API_ID,
            'timestamp': datetime.now().isoformat(),
        },
        'response': {
            'exists': count > 0,
            'numTotalResults': count,
            'results': results,
        },
    }


# Declared in meta.returnedSchemas when a response carries genomicVariation
# data beyond the default boolean shape (e.g. allele frequencies at
# 'aggregated' granularity).
GENOMIC_VARIATION_SCHEMA = {
    'entityType': 'genomicVariation',
    'schema': (
        'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/'
        'json/beacon-v2-default-model/genomicVariations/defaultSchema.json'
    ),
}


def build_meta(returned_granularity='boolean', received_request=None, returned_schemas=None):
    """
    Beacon v2 spec meta envelope. Default granularity is 'boolean'; callers
    serving richer data (e.g. allele frequencies) pass 'aggregated' and the
    matching `returned_schemas`.
    """
    meta = {
        'beaconId': settings.BEACON_API_ID,
        'apiVersion': 'v2.0.0',
        'returnedGranularity': returned_granularity,
        'returnedSchemas': returned_schemas if returned_schemas is not None else [],
    }
    if received_request is not None:
        meta['receivedRequestSummary'] = received_request
    return meta


MAX_ECHOED_SCHEMAS = 10
MAX_ECHOED_SCHEMA_LENGTH = 256

# Mirrors BeaconQuerySerializer.requestedGranularity's choices.
VALID_GRANULARITIES = ('boolean', 'count', 'aggregated', 'record')


def _echoed_schemas(validated_params):
    """The client's requestedSchemas, echoed only if they are plainly safe.

    `validated_params` can be an untouched POST body (individual_query_boolean
    passes exactly that), so this value is attacker-controlled and of unknown
    type. Only a list of short strings is reflected; anything else reports the
    truth for a request that named no usable schema, which is `[]`.
    """
    raw = validated_params.get('requestedSchemas') if isinstance(validated_params, dict) else None
    if not isinstance(raw, (list, tuple)):
        return []
    return [
        item[:MAX_ECHOED_SCHEMA_LENGTH]
        for item in list(raw)[:MAX_ECHOED_SCHEMAS]
        if isinstance(item, str) and item.strip()
    ]


def _echoed_pagination(validated_params):
    """The skip/limit that were actually applied to this request.

    Falls back to `parse_pagination` when the caller passed a raw request
    mapping rather than serializer output, and to the defaults when the value
    cannot be parsed at all — a summary is never worth failing a response over,
    and an unparseable value already produced a 400 on the query path.
    """
    if not isinstance(validated_params, dict):
        return {'skip': DEFAULT_SKIP, 'limit': DEFAULT_LIMIT}

    skip = validated_params.get('skip')
    limit = validated_params.get('limit')
    if isinstance(skip, int) and not isinstance(skip, bool) and \
            isinstance(limit, int) and not isinstance(limit, bool):
        # Already resolved by validate_query_request / parse_pagination.
        return {'skip': skip, 'limit': limit}

    try:
        skip, limit = parse_pagination(validated_params)
    except InvalidPagination:
        return {'skip': DEFAULT_SKIP, 'limit': DEFAULT_LIMIT}
    return {'skip': skip, 'limit': limit}


def build_received_request_summary(validated_params=None, granularity='boolean'):
    """
    Beacon v2 spec receivedRequestSummary.

    Every field here describes what the client actually asked for. That was
    not previously true: `validated_params` was ignored outright and the
    pagination block was the constant `{'skip': 0, 'limit': 10}`, so the
    beacon reported a page it had never applied — to a client that had never
    requested one. A summary that does not summarise the request is worse than
    no summary, because a client has no way to tell it is being lied to.

    `requestParameters` is omitted intentionally: the spec types it as an
    object whose schema varies per entry type, and echoing the raw dict fails
    schema validation. Verifier-required fields are present below.
    """
    params = validated_params if isinstance(validated_params, dict) else {}

    # An explicit requestedGranularity in the request wins over the caller's
    # default, so the echo reflects the client rather than our fallback. Only
    # a spec-valid value is echoed: this can be a raw, unvalidated body (see
    # individual_query_boolean), and reflecting an arbitrary attacker string
    # back into the response is not something a summary needs to do.
    requested = params.get('requestedGranularity')
    if requested not in VALID_GRANULARITIES:
        requested = granularity

    return {
        'apiVersion': 'v2.0.0',
        'requestedGranularity': requested,
        'requestedSchemas': _echoed_schemas(params),
        'pagination': _echoed_pagination(params),
    }


def build_info_envelope(payload):
    """Beacon v2 envelope for /info, /configuration, /map, /entry_types."""
    return {'meta': build_meta(), 'response': payload}


def build_default_handovers():
    """
    Top-level Beacon v2 handovers for the AfriGen-D Beacon.

    Underlying genomic data is NOT downloadable and there is no data-access
    application process. The data is usable only via the AfriGen-D Federated
    Imputation Service, where queries are computed against the reference
    panel without exposing the raw genotypes. The handover points discoverers
    at that service.
    """
    imputation_url = getattr(settings, 'BEACON_IMPUTATION_URL', None)
    if not imputation_url:
        return []
    return [{
        'handoverType': {
            'id': 'CUSTOM:FEDERATED_IMPUTATION',
            'label': 'AfriGen-D Federated Imputation Service',
        },
        'url': imputation_url,
        'note': (
            'The underlying genomic data is not available for download. '
            'It can only be used through the AfriGen-D Federated Imputation '
            'Service, which lets you submit your own genotypes for imputation '
            'against this reference panel without exposing the raw data.'
        ),
    }]


def build_query_envelope(exists, num_total=0, result_sets=None, validated_params=None,
                         requested_granularity='boolean', returned_granularity='boolean'):
    """
    Beacon v2 envelope for query endpoints.
    Spec: {meta, responseSummary, response: {resultSets, beaconHandovers}}

    Default granularity is 'boolean' (backward compatible). When the caller
    serves allele frequencies it passes returned_granularity='aggregated',
    which also declares the genomicVariation schema in meta.returnedSchemas.
    """
    returned_schemas = (
        [GENOMIC_VARIATION_SCHEMA]
        if returned_granularity in ('aggregated', 'record')
        else None
    )
    return {
        'meta': build_meta(
            returned_granularity=returned_granularity,
            received_request=build_received_request_summary(
                validated_params, granularity=requested_granularity
            ),
            returned_schemas=returned_schemas,
        ),
        'responseSummary': {
            'exists': bool(exists),
            'numTotalResults': int(num_total),
        },
        'response': {
            'resultSets': result_sets or [],
            'beaconHandovers': build_default_handovers(),
        },
    }


def extract_error_message(detail, fallback='Invalid request'):
    """
    Flatten a DRF validation error `detail` into one human-readable sentence.

    `serializer.is_valid(raise_exception=True)` raises a ValidationError whose
    `.detail` is a nested structure of dicts/lists of `ErrorDetail` (a str
    subclass). Passing that to `str()` yields the raw Python repr, which is
    what production was leaking:

        "{'non_field_errors': [ErrorDetail(string='Invalid chromosome: 999',
         code='invalid')]}"

    Only the message strings are kept. Field names and error codes are
    deliberately dropped: they describe our serializer's internal shape, not
    anything the caller can act on.
    """
    messages = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif node is not None:
            # ErrorDetail subclasses str; str() gives the message alone.
            text = str(node).strip()
            if text and text not in messages:
                messages.append(text)

    walk(detail)
    if not messages:
        return fallback
    return ' '.join(m if m.endswith(('.', '!', '?')) else f'{m}.' for m in messages)


def build_error_envelope(error_code, error_message):
    """
    Beacon v2 error envelope: {meta, error: {errorCode, errorMessage}}.

    Uses the same `meta` block as the success envelopes so a client can parse
    `meta` uniformly regardless of outcome.
    """
    return {
        'meta': build_meta(),
        'error': {
            'errorCode': int(error_code),
            'errorMessage': str(error_message),
        },
    }


def build_collection_envelope(items, set_type='dataset', set_id='public',
                              validated_params=None, num_total=None):
    """
    Beacon v2 envelope for collection endpoints (/filtering_terms).

    Delegates to :func:`build_query_envelope` so a collection endpoint is
    byte-for-byte the same shape as /datasets and /cohorts. It previously
    emitted only `{meta, response}` — no `responseSummary`, no
    `beaconHandovers`, no `receivedRequestSummary` — which made
    /filtering_terms structurally different from every sibling endpoint. The
    GA4GH verifier checks envelope shape, so that drift is exactly what it
    should have caught and did not; keeping one implementation removes the
    place where the two can diverge again.

    `num_total` is the size of the whole collection when `items` is one page
    of it, so `responseSummary.numTotalResults` stays a total rather than
    silently becoming a page size.
    """
    result_sets = [{
        'id': set_id,
        'setType': set_type,
        'exists': len(items) > 0,
        'resultsCount': len(items),
        'results': items,
    }] if items else []

    total = len(items) if num_total is None else num_total
    return build_query_envelope(
        exists=total > 0,
        num_total=total,
        result_sets=result_sets,
        validated_params=validated_params,
    )


class BooleanResponseMixin:
    """
    Mixin for views to automatically convert responses to boolean format
    """
    
    def finalize_response(self, request, response, *args, **kwargs):
        """Override to transform response to boolean if needed"""
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # Only transform successful responses in boolean mode
        if (settings.BEACON_RESPONSE_MODE == 'BOOLEAN' and 
            response.status_code == 200 and 
            hasattr(response, 'data')):
            
            response.data = transform_to_boolean_response(response.data)
        
        return response
