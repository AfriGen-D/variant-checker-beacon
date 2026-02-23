"""
GA4GH Beacon v2 API - Secure Django Settings
This file replaces the original settings.py with secure, environment-based configuration
"""

import os
import sys
from pathlib import Path
import mongoengine
from decouple import config, Csv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# Hosts/domain names that are valid for this site
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Security Headers and Settings
if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
    SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)
    SECURE_CONTENT_TYPE_NOSNIFF = config('SECURE_CONTENT_TYPE_NOSNIFF', default=True, cast=bool)
    SECURE_BROWSER_XSS_FILTER = config('SECURE_BROWSER_XSS_FILTER', default=True, cast=bool)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    SESSION_COOKIE_HTTPONLY = config('SESSION_COOKIE_HTTPONLY', default=True, cast=bool)
    SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Strict')
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_HTTPONLY = config('CSRF_COOKIE_HTTPONLY', default=True, cast=bool)
    X_FRAME_OPTIONS = config('X_FRAME_OPTIONS', default='DENY')

# ============================================================================
# APPLICATION DEFINITION
# ============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',  # JWT authentication
    'corsheaders',
    'beacon_api',
    'drf_spectacular',
    'django_ratelimit',  # Rate limiting
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
]

ROOT_URLCONF = 'beacon_project.urls'

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
# DATABASE CONFIGURATION
# ============================================================================

# Django ORM database (for admin/auth)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.dummy',
    }
}

# MongoDB Configuration with authentication
MONGODB_HOST = config('MONGODB_HOST', default='localhost')
MONGODB_PORT = config('MONGODB_PORT', default=27017, cast=int)
MONGODB_NAME = config('MONGODB_NAME', default='beacon_db')
MONGODB_USERNAME = config('MONGODB_USERNAME', default=None)
MONGODB_PASSWORD = config('MONGODB_PASSWORD', default=None)
MONGODB_AUTH_SOURCE = config('MONGODB_AUTH_SOURCE', default='admin')
MONGODB_AUTH_MECHANISM = config('MONGODB_AUTH_MECHANISM', default='SCRAM-SHA-256')

# Build MongoDB URI with authentication if credentials provided
if MONGODB_USERNAME and MONGODB_PASSWORD:
    MONGODB_URI = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_NAME}?authSource={MONGODB_AUTH_SOURCE}&authMechanism={MONGODB_AUTH_MECHANISM}"
else:
    MONGODB_URI = config('MONGODB_URI', default=f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/')

# Connect to MongoDB using MongoEngine
try:
    mongoengine.connect(
        db=MONGODB_NAME,
        host=MONGODB_URI,
        alias='default',
        connect=False,  # Defer connection until needed
        tz_aware=True,  # Handle timezone
        serverSelectionTimeoutMS=5000,  # 5 second timeout
    )
    if not DEBUG:
        print(f"Connected to MongoDB database: {MONGODB_NAME}")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

REDIS_HOST = config('REDIS_HOST', default='localhost')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
REDIS_PASSWORD = config('REDIS_PASSWORD', default='')
REDIS_DB = config('REDIS_DB', default=0, cast=int)
CACHE_TIMEOUT = config('REDIS_CACHE_TIMEOUT', default=300, cast=int)  # 5 minutes

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'PASSWORD': REDIS_PASSWORD if REDIS_PASSWORD else None,
        },
        'KEY_PREFIX': 'beacon_cache',
        'TIMEOUT': CACHE_TIMEOUT,
    }
}

# ============================================================================
# AUTHENTICATION CONFIGURATION
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': config('JWT_ALGORITHM', default='HS256'),
    'SIGNING_KEY': config('JWT_SECRET_KEY', default=SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    
    'AUTH_HEADER_TYPES': (config('JWT_AUTH_HEADER_PREFIX', default='Bearer'),),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# ============================================================================
# CORS CONFIGURATION
# ============================================================================

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', 
    default='http://localhost:3000,http://localhost:8000', 
    cast=Csv())

CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

if CORS_ALLOW_ALL_ORIGINS:
    # Override specific origins if allowing all
    CORS_ALLOWED_ORIGINS = []

# Additional CORS settings
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ============================================================================
# REST FRAMEWORK CONFIGURATION
# ============================================================================

# Feature flags
FEATURE_AUTHENTICATION_ENABLED = config('FEATURE_AUTHENTICATION_ENABLED', default=True, cast=bool)
FEATURE_RATE_LIMITING_ENABLED = config('FEATURE_RATE_LIMITING_ENABLED', default=True, cast=bool)

# Build REST Framework settings based on feature flags
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': config('API_PAGE_SIZE', default=25, cast=int),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v2',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',
}

# Authentication settings
if FEATURE_AUTHENTICATION_ENABLED:
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ]
    REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ]
else:
    REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = [
        'rest_framework.permissions.AllowAny',
    ]

# Rate limiting settings
if FEATURE_RATE_LIMITING_ENABLED:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ]
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
        'anon': config('RATELIMIT_DEFAULT', default='100/hour'),
        'user': config('RATELIMIT_DEFAULT', default='1000/hour'),
    }

# ============================================================================
# API DOCUMENTATION CONFIGURATION
# ============================================================================

SPECTACULAR_SETTINGS = {
    'TITLE': config('BEACON_API_NAME', default='GA4GH Beacon v2 API'),
    'DESCRIPTION': 'GA4GH Beacon v2 API implementation for genomic data discovery. Fully compliant with official Beacon v2 specification - query-only operations for data discovery.',
    'VERSION': config('BEACON_API_VERSION', default='2.0.0'),
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
    'CONTACT': {
        'name': 'GA4GH Beacon API',
        'url': 'https://docs.genomebeacons.org/',
    },
    'LICENSE': {
        'name': 'CC0 1.0 Universal',
        'url': 'https://creativecommons.org/publicdomain/zero/1.0/',
    },
    'EXTERNAL_DOCS': {
        'description': 'Beacon v2 Documentation',
        'url': 'https://docs.genomebeacons.org/',
    },
    'TAGS': [
        {
            'name': 'Beacon Core',
            'description': 'Core Beacon v2 endpoints for service information'
        },
        {
            'name': 'Data Discovery',
            'description': 'Query endpoints for genomic and phenotypic data discovery'
        },
        {
            'name': 'Authentication',
            'description': 'JWT authentication endpoints'
        },
        {
            'name': 'Configuration',
            'description': 'Beacon configuration and metadata endpoints'
        }
    ],
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development server'},
    ],
}

# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = config('DJANGO_LANGUAGE_CODE', default='en-us')
TIME_ZONE = config('DJANGO_TIME_ZONE', default='UTC')
USE_I18N = config('DJANGO_USE_I18N', default=True, cast=bool)
USE_TZ = config('DJANGO_USE_TZ', default=True, cast=bool)

# ============================================================================
# STATIC FILES CONFIGURATION
# ============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOG_FORMAT = config('LOG_FORMAT', default='json')

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'verbose' if DEBUG else LOG_FORMAT,
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'beacon.log'),
            'maxBytes': config('LOG_MAX_BYTES', default=10485760, cast=int),  # 10MB
            'backupCount': config('LOG_BACKUP_COUNT', default=5, cast=int),
            'formatter': 'json',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'errors.log'),
            'maxBytes': config('LOG_MAX_BYTES', default=10485760, cast=int),  # 10MB
            'backupCount': config('LOG_BACKUP_COUNT', default=5, cast=int),
            'formatter': 'json',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'security.log'),
            'maxBytes': config('LOG_MAX_BYTES', default=10485760, cast=int),  # 10MB
            'backupCount': config('LOG_BACKUP_COUNT', default=5, cast=int),
            'formatter': 'json',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'beacon_api': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG' if DEBUG else LOG_LEVEL,
            'propagate': False,
        },
        'mongoengine': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ============================================================================
# MISCELLANEOUS
# ============================================================================

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Beacon-specific settings
BEACON_API_ID = config('BEACON_API_ID', default='org.ga4gh.beacon')
BEACON_ORGANIZATION_ID = config('BEACON_ORGANIZATION_ID', default='ga4gh')
BEACON_ORGANIZATION_NAME = config('BEACON_ORGANIZATION_NAME', default='Global Alliance for Genomics and Health')

# Monitoring
METRICS_ENABLED = config('METRICS_ENABLED', default=True, cast=bool)
HEALTH_CHECK_ENABLED = config('HEALTH_CHECK_ENABLED', default=True, cast=bool)

# Email configuration (optional)
if config('EMAIL_HOST', default=None):
    EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = config('EMAIL_HOST')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@beacon.org')