"""
GA4GH Beacon v2 API - Boolean Response Settings
Simplified configuration for public YES/NO discovery only
"""

import os
from pathlib import Path
from urllib.parse import quote_plus

import mongoengine
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# Error tracking — GlitchTip (Sentry-protocol). No-op when SENTRY_DSN is unset.
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import re
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    # DRF's Throttled exception puts the remaining-seconds count in the
    # message, so each rate-limit denial fingerprints as a separate issue
    # ("in 21 seconds", "in 51 seconds", ...). Collapse the family into one
    # issue and demote it to "warning" — rate-limit denial is operational,
    # not a bug.
    _THROTTLE_SECONDS_RE = re.compile(r"in \d+ seconds?")

    def _beacon_before_send(event, hint):
        for v in (event.get('exception') or {}).get('values') or ():
            if v.get('type') == 'Throttled':
                event['fingerprint'] = ['beacon-api-throttled']
                event['level'] = 'warning'
                if 'value' in v:
                    v['value'] = _THROTTLE_SECONDS_RE.sub(
                        "in N seconds", v['value']
                    )
                break
        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config('SENTRY_ENVIRONMENT', default='dev'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
        before_send=_beacon_before_send,
    )

# ============================================================================
# SECURITY CONFIGURATION - MINIMAL FOR PUBLIC API
# ============================================================================

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Basic Security Headers (no auth needed)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# HSTS — only has effect when served over TLS (Cloudflare Tunnel terminates TLS)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ============================================================================
# APPLICATION DEFINITION - MINIMAL
# ============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'beacon_api',
    'drf_spectacular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'beacon_api.middleware.RateLimitMiddleware',  # Custom rate limiting
    'beacon_api.middleware.QueryLogMiddleware',   # Audit log -> MongoDB query_logs
]

ROOT_URLCONF = 'beacon_project.urls_boolean'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'beacon_project.wsgi.application'

# ============================================================================
# DATABASE - READ-ONLY MONGODB
# ============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.dummy',
    }
}

# MongoDB
#
# Credentials are OPTIONAL so one settings file serves both hosts: the
# production beacon runs Mongo with authentication enabled, the API sidecar
# does not. Hard-coding the unauthenticated URI meant an image built from this
# repo connected fine to prod's Mongo and then failed every read with
# "command aggregate requires authentication" — a container that reports
# healthy while answering nothing.
MONGODB_HOST = config('MONGODB_HOST', default='localhost')
MONGODB_PORT = config('MONGODB_PORT', default=27017, cast=int)
MONGODB_NAME = config('MONGODB_NAME', default='beacon_db')
MONGODB_USERNAME = config('MONGODB_USERNAME', default='')
MONGODB_PASSWORD = config('MONGODB_PASSWORD', default='')

if MONGODB_USERNAME:
    # Percent-encode the credentials: a password containing @ : / or ? would
    # otherwise be parsed as URI structure and produce a confusing auth error.
    _user = quote_plus(MONGODB_USERNAME)
    _password = quote_plus(MONGODB_PASSWORD)
    MONGODB_URI = (
        f'mongodb://{_user}:{_password}@{MONGODB_HOST}:{MONGODB_PORT}/'
        f'{MONGODB_NAME}?authSource={MONGODB_NAME}'
    )
else:
    MONGODB_URI = f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_NAME}'

mongoengine.connect(
    db=MONGODB_NAME,
    host=MONGODB_URI,
    alias='default',
    connect=False,
    serverSelectionTimeoutMS=5000,
    # This beacon is read-only; retryable writes need a replica set and error
    # on a standalone mongod.
    retryWrites=False,
)

# ============================================================================
# CACHE - OPTIONAL BUT RECOMMENDED
# ============================================================================

REDIS_HOST = config('REDIS_HOST', default='localhost')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
CACHE_TIMEOUT = config('REDIS_CACHE_TIMEOUT', default=300, cast=int)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # Bound cache I/O so a slow/hung Redis can't block request workers
            # indefinitely (boolean mode previously set no timeouts).
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'beacon_boolean',
        'TIMEOUT': CACHE_TIMEOUT,
    }
}

# ============================================================================
# CORS - FULLY OPEN FOR PUBLIC API
# ============================================================================

CORS_ALLOW_ALL_ORIGINS = True  # Public API
CORS_ALLOW_CREDENTIALS = False  # No authentication

# ============================================================================
# REST FRAMEWORK - PUBLIC ACCESS WITH RATE LIMITING
# ============================================================================

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Public access
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('RATELIMIT_DEFAULT', default='100/hour'),
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'beacon_api.utils.custom_exception_handler',
}

# ============================================================================
# BEACON CONFIGURATION - BOOLEAN ONLY
# ============================================================================

BEACON_RESPONSE_MODE = config('BEACON_RESPONSE_MODE', default='BOOLEAN')
BEACON_HIDE_DETAILED_DATA = config('BEACON_HIDE_DETAILED_DATA', default=True, cast=bool)
BEACON_API_VERSION = config('BEACON_API_VERSION', default='v2.0.0')
BEACON_API_ID = config('BEACON_API_ID', default='org.afrigen-d.beacon')
BEACON_API_NAME = config('BEACON_API_NAME', default='AfriGen-D Beacon')
BEACON_ORGANIZATION_ID = config('BEACON_ORGANIZATION_ID', default='org.afrigen-d')
BEACON_ORGANIZATION_NAME = config('BEACON_ORGANIZATION_NAME', default='AfriGen-D')
BEACON_WELCOME_URL = config('BEACON_WELCOME_URL', default='https://afrigen-d.org')
BEACON_SERVICE_URL = config('BEACON_SERVICE_URL', default='https://beacon.afrigen-d.org/api/')
BEACON_ORGANIZATION_URL = config('BEACON_ORGANIZATION_URL', default='https://afrigen-d.org')
BEACON_CONTACT_URL = config('BEACON_CONTACT_URL', default='mailto:support@bioinformaticsinstitute.africa')
BEACON_IMPUTATION_URL = config('BEACON_IMPUTATION_URL', default='https://fedimpute.afrigen-d.org')

# Rate limits for specific endpoints
BEACON_RATE_LIMITS = {
    'query': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
    'variants': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
    'individuals': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
    # Discovery/metadata only. Federation partners and registries poll these
    # on a fixed cadence, so the budget has to comfortably exceed the sum of
    # their schedules plus normal browsing.
    'discovery': config('RATELIMIT_DISCOVERY_ENDPOINT', default='1000/hour'),
}

# ============================================================================
# PRIVACY / DISCLOSURE CONTROL
# ============================================================================

# How long a query_logs row survives before the MongoDB TTL index deletes it.
# A row pairs a requester with the exact genomic locus queried, so it is
# personal data and cannot be kept indefinitely. 90 days = one full quarter,
# which is what an abuse or access review actually needs and what the longest
# Grafana dashboard window covers. Applied per row at write time, so a change
# here affects new rows only. See beacon_api/models.py::QueryLog.
BEACON_QUERYLOG_RETENTION_DAYS = config(
    'BEACON_QUERYLOG_RETENTION_DAYS', default=90, cast=int
)

# Published allele-frequency precision. An unrounded AF is a carrier count in
# disguise (AF == k/2N inverts to k), which is the Homer / Shringarpure-
# Bustamante re-identification primitive. The rounding step must be coarser
# than 1/2N: the V6HC-S_AFR panel has 1,895 samples (2N = 3,790), so
# 1/2N ~ 0.00026 and a 3-decimal grid is ~4x coarser. Reduce `decimals` for a
# smaller cohort. Does NOT affect the boolean `exists` answer.
BEACON_AF_DECIMALS = config('BEACON_AF_DECIMALS', default=3, cast=int)

# Small-cell suppression floor: frequencies below this are withheld entirely,
# because rounding alone cannot protect the rarest (most identifying)
# variants. 0.01 is ~38 alleles in the AFR panel, well above the conventional
# "at least 5 per cell" rule.
BEACON_AF_MIN_PUBLISHED = config('BEACON_AF_MIN_PUBLISHED', default=0.01, cast=float)

# Server-side time budget for a single MongoDB query, in milliseconds, applied
# via max_time_ms(). MongoDB kills the operation when it expires and the worker
# is released immediately.
#
# This is the backstop for query cost, and it is the only bound that holds in
# the worst case: a `limit` does not bound a query that matches nothing,
# because the server still scans the entire collection looking for documents to
# fill the page. Before this existed, an unparameterized GET /api/g_variants
# ran for 30.7s and returned HTTP 504 — unauthenticated and trivially
# repeatable, so with `--workers 4` four concurrent requests saturated the API.
#
# 5s is well above any indexed locus query (single-digit ms) and well below the
# 30s gateway timeout, so a refused query is refused by us, with an actionable
# message, rather than by nginx with a 504.
BEACON_QUERY_MAX_TIME_MS = config(
    'BEACON_QUERY_MAX_TIME_MS', default=5000, cast=int
)

# How far before the queried position a stored variant may begin and still be
# considered, in bases. This exists for the {reference_name, start} index:
# without a lower bound, `start < query_end` is walked from the first variant on
# the chromosome, so query cost grows with genomic coordinate. Measured on the
# 42M-variant panel, an unbounded lookup at chr2:178.5M took 3.6s warm (22s
# cold); bounded to a 1kb window it took 2ms.
#
# The trade-off is explicit: a variant LONGER than this that overlaps the
# queried position from below will not be found. 10kb is comfortably above the
# longest variant a short-read SNV/indel reference panel produces, while still
# keeping the index range narrow. Raise it if structural variants are loaded —
# scan cost grows roughly in proportion.
BEACON_MAX_VARIANT_SPAN = config(
    'BEACON_MAX_VARIANT_SPAN', default=10000, cast=int
)

# ============================================================================
# API DOCUMENTATION
# ============================================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'GA4GH Beacon v2 API - Public Discovery',
    'DESCRIPTION': 'Public boolean discovery service for genomic variants. Returns only YES/NO responses.',
    'VERSION': '2.0.0-boolean',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {
        'name': 'AfriGen-D Beacon',
        'url': 'https://afrigen-d.org',
    },
}

# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================================================
# STATIC FILES
# ============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================================
# LOGGING - SIMPLIFIED
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/beacon.log',
            'maxBytes': 10485760,
            'backupCount': 3,
            'formatter': 'simple',
        },
    },
    'loggers': {
        'beacon_api': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
        },
    },
}

# Create logs directory
os.makedirs('logs', exist_ok=True)

# ============================================================================
# MISCELLANEOUS
# ============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'