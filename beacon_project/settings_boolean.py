"""
GA4GH Beacon v2 API - Boolean Response Settings
Simplified configuration for public YES/NO discovery only
"""

import os
from pathlib import Path
import mongoengine
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

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
BEACON_API_VERSION = 'v2.0.0'
BEACON_API_ID = 'org.afrigend.beacon'
BEACON_API_NAME = 'AfriGEND Beacon'
BEACON_ORGANIZATION_ID = 'org.afrigend'
BEACON_ORGANIZATION_NAME = 'AfriGEND'

# Rate limits for specific endpoints
BEACON_RATE_LIMITS = {
    'query': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
    'variants': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
    'individuals': config('RATELIMIT_QUERY_ENDPOINT', default='50/hour'),
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
        'name': 'AfriGEND Beacon',
        'url': 'https://afrigend.org',
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