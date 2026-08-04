"""
GA4GH Beacon v2 API - Boolean Response Settings
Simplified configuration for public YES/NO discovery only
"""

import os
from pathlib import Path
import mongoengine
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# Error tracking — GlitchTip (Sentry-protocol). No-op when SENTRY_DSN is unset.
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config('SENTRY_ENVIRONMENT', default='dev'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
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

# MongoDB - No authentication for read-only boolean responses
MONGODB_HOST = config('MONGODB_HOST', default='localhost')
MONGODB_PORT = config('MONGODB_PORT', default=27017, cast=int)
MONGODB_NAME = config('MONGODB_NAME', default='beacon_db')

mongoengine.connect(
    db=MONGODB_NAME,
    host=f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/',
    alias='default',
    connect=False,
    serverSelectionTimeoutMS=5000,
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