"""
Django settings for testing with MongoDB using MongoEngine
"""

import os
from pathlib import Path
import mongoengine
from mongoengine.connection import connect, disconnect

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-a6fs2g5%0=$b-+w!u*g-q$hg^loe5n-hv_i0=yc0(k#b-)!0$&'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
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

# Database - Use SQLite for testing flush operations
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Use in-memory database for testing
    }
}

# MongoEngine settings
MONGODB_TEST_DB = 'test_beacon_db'  # Separate test database
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://mongodb:27017/')

# Disconnect if already connected
disconnect()

# Connect to MongoDB using MongoEngine for testing - disabling auto index creation
connect(
    db=MONGODB_TEST_DB,
    host=MONGODB_URI,
    alias='default',
    connect=False,  # Defer connection until needed
    tz_aware=True,  # Handle timezone
)

# Register a setup hook to properly clean test data
from django.test.runner import DiscoverRunner

class MongoEngineTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        from mongoengine.connection import get_db
        get_db().client.drop_database(MONGODB_TEST_DB)
        return super().setup_databases(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        from mongoengine.connection import get_db
        get_db().client.drop_database(MONGODB_TEST_DB)
        return super().teardown_databases(old_config, **kwargs)

TEST_RUNNER = 'beacon_project.test_settings.MongoEngineTestRunner'

print(f"Connected to MongoDB test database at {MONGODB_URI} with database {MONGODB_TEST_DB}")

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Cache settings for testing
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Testing flag
TESTING = True

# Disable caching during tests
CACHE_TIMEOUT = 0 