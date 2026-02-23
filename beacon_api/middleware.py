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
            
            # Create cache key
            cache_key = f'rate_limit:{ip}:{endpoint}'
            
            # Get current count
            current = cache.get(cache_key, 0)
            
            if current >= count:
                return False
            
            # Increment counter
            cache.set(cache_key, current + 1, period_seconds)
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