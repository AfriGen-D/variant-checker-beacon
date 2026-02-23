"""
Utility functions for Beacon API
"""
import logging
from django.conf import settings
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

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