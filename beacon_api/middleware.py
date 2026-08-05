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


class QueryLogMiddleware:
    """
    Records each beacon API query into MongoDB (collection: query_logs) for
    audit, dashboard metrics, and debugging. Best-effort: any DB write failure
    is swallowed so the beacon response is never blocked.
    Skips internal/service endpoints (info, configuration, entry_types, map,
    service-info, health) — only logs actual data-discovery queries.
    """

    # Path *prefixes* (after /api) that are real beacon queries.
    LOGGED_PREFIXES = (
        '/api/g_variants', '/api/individuals', '/api/biosamples',
        '/api/cohorts', '/api/analyses', '/api/datasets',
        '/api/filtering_terms', '/api/query',
    )
    # Subpaths that are metadata, not queries — skip.
    SKIP_SUFFIXES = ('/info', '/health', '/configuration', '/entry_types', '/map', '/service-info')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if self._should_log(request.path):
            try:
                self._record(request, response, elapsed_ms)
            except Exception as e:
                # Never block the response on a logging failure.
                logger.warning(f"QueryLog write failed: {e}")

        return response

    def _should_log(self, path):
        if not any(path.startswith(p) for p in self.LOGGED_PREFIXES):
            return False
        if any(path.endswith(s) for s in self.SKIP_SUFFIXES):
            return False
        return True

    def _record(self, request, response, elapsed_ms):
        # Lazy import to avoid Django app-loading issues at module import time.
        from beacon_api.models import QueryLog

        query_type = self._extract_query_type(request.path)
        params = dict(request.GET.lists()) if request.method == 'GET' else {}
        if request.method == 'POST' and request.content_type == 'application/json':
            try:
                import json as _json
                body = request.body.decode('utf-8') if request.body else ''
                if body:
                    params['_body'] = _json.loads(body)
            except Exception:
                pass

        hits = self._extract_hits(response)
        ip = self._client_ip(request)

        QueryLog(
            query_type=query_type,
            query_params=params,
            response_status=response.status_code,
            response_time_ms=elapsed_ms,
            hits_count=hits,
            client_ip=ip,
        ).save()

    @staticmethod
    def _extract_query_type(path):
        # /api/g_variants/<id> -> g_variants  ;  /api/query -> query
        parts = path.strip('/').split('/')
        # parts == ['api', '<entry>', ...]  -> '<entry>'
        return parts[1] if len(parts) >= 2 else 'unknown'

    @staticmethod
    def _extract_hits(response):
        # Best-effort: parse JSON body for resultSets[].resultsCount summed.
        try:
            content_type = response.get('Content-Type', '') if hasattr(response, 'get') else ''
            if 'application/json' not in content_type:
                return 0
            import json as _json
            body = response.content.decode('utf-8') if response.content else '{}'
            data = _json.loads(body)
            # Beacon v2 shape: {"responseSummary": {"numTotalResults": N, "exists": bool}, ...}
            rs = data.get('responseSummary') or {}
            if 'numTotalResults' in rs:
                return int(rs['numTotalResults'] or 0)
            if rs.get('exists') is True:
                return 1
            # Fallback: count items in 'response.resultSets[*].resultsCount'
            sets = (data.get('response') or {}).get('resultSets') or []
            return sum(int(s.get('resultsCount') or 0) for s in sets)
        except Exception:
            return 0

    @staticmethod
    def _client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
