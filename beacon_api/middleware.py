"""
Custom middleware for Beacon API
"""
import time
import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger('beacon_api')


class RateLimitMiddleware:
    """
    Simple rate limiting middleware for public API protection
    """

    # Spec/discovery endpoints — metadata only, no genomic data. Matched on any
    # path segment so both /api/datasets and /api/datasets/<id> qualify.
    DISCOVERY_ENDPOINTS = frozenset({
        'info', 'service-info', 'configuration', 'entry_types', 'map',
        'datasets', 'cohorts', 'filtering_terms',
    })

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = getattr(settings, 'BEACON_RATE_LIMITS', {})
        self.default_limit = '100/hour'
        
    def __call__(self, request):
        # Only rate limit API endpoints (skip health check)
        if request.path.startswith('/api/') and request.path.rstrip('/') != '/api/health':
            # Get client IP
            ip = self.get_client_ip(request)
            
            # Check rate limit for specific endpoints
            endpoint_key = self.get_endpoint_key(request.path)
            limit_config = self.rate_limits.get(endpoint_key, self.default_limit)
            
            if not self.check_rate_limit(ip, endpoint_key, limit_config):
                logger.warning(f"Rate limit exceeded for IP {ip} on endpoint {endpoint_key}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Limit is {limit_config}',
                }, status=429)
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_endpoint_key(self, path):
        """Extract endpoint key from path"""
        # Map paths to rate limit keys
        if '/query' in path:
            return 'query'
        elif '/g_variants' in path:
            return 'variants'
        elif '/individuals' in path:
            return 'individuals'
        elif set(path.strip('/').split('/')) & self.DISCOVERY_ENDPOINTS:
            # Cheap, cacheable metadata. Beacon Network aggregators and GA4GH
            # registries poll these continuously, so they need a far larger
            # budget than data queries or federation partners get throttled
            # out and report this beacon as down.
            return 'discovery'
        else:
            return 'default'
    
    def check_rate_limit(self, ip, endpoint, limit_config):
        """Check if request is within rate limit"""
        # Parse limit config (e.g., "100/hour")
        try:
            count, period = limit_config.split('/')
            count = int(count)
            
            # Convert period to seconds
            period_seconds = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400,
            }.get(period, 3600)
            
            # Bucket the key by wall-clock window. Deriving the window from the
            # clock — rather than relying on the key's TTL to end it — is what
            # makes the counter actually roll over: a new window is a new key.
            # Keying without the window is a latch, because cache.set() pushed
            # the expiry forward on every accepted request, so a client polling
            # more often than once per period never got a fresh window and
            # stayed blocked once it hit the limit.
            window = int(time.time()) // period_seconds
            cache_key = f'rate_limit:{ip}:{endpoint}:{window}'

            # Get current count
            current = cache.get(cache_key, 0)

            if current >= count:
                return False

            # Increment counter. The TTL is only a cleanup mechanism now — it
            # outlives the window so a key can never survive into the next one.
            cache.set(cache_key, current + 1, period_seconds + 60)
            return True

        except Exception as e:
            logger.error(f"Error parsing rate limit: {e}")
            return True  # Allow on error


class BooleanResponseMiddleware:
    """
    Middleware to ensure only boolean responses for public API
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.boolean_mode = getattr(settings, 'BEACON_RESPONSE_MODE', 'FULL') == 'BOOLEAN'
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only modify API responses in boolean mode
        if self.boolean_mode and request.path.startswith('/api/'):
            # This will be handled in the views
            pass
            
        return response