# Beacon Project

This directory contains the Django project configuration for the GA4GH Beacon v2 API using MongoDB with MongoEngine.

## Directory Structure

- **beacon_api/**: [Symlink] Reference to the main Beacon API application.

## Key Files

- **__init__.py**: Python package initialization file.
- **asgi.py**: ASGI application entrypoint for asynchronous web servers.
- **settings.py**: Main Django settings for the entire project.
  - Configures MongoDB connection with MongoEngine
  - Sets up installed applications
  - Configures Django REST Framework
  - Defines authentication settings
- **test_settings.py**: Settings specific to the test environment.
  - Configures test-specific MongoDB connection
  - Sets up a separate test database
  - Configures test runners for MongoDB
- **urls.py**: URL routing configuration for the Django project.
  - Root URL configuration
  - Includes Beacon API URLs
  - Sets up admin interface and API documentation
- **wsgi.py**: WSGI application entrypoint for traditional web servers.

## MongoDB Configuration

The project uses MongoEngine to connect to MongoDB:

```python
# MongoEngine settings
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DB = os.environ.get('MONGODB_DB', 'beacon_db')

# Connect to MongoDB using MongoEngine
mongoengine.connect(
    db=MONGODB_DB,
    host=MONGODB_URI,
    alias='default',
    connect=False,  # Defer connection until needed
    tz_aware=True,  # Handle timezone
)
```

## API Documentation

The project includes automatic API documentation using drf-spectacular:

- `/api/schema/`: OpenAPI schema endpoint
- `/api/docs/`: Swagger UI for interactive API documentation

## Purpose

The beacon_project directory serves as the main Django project container that integrates the Beacon API application. It provides the necessary configuration for running the API as a Django web application with MongoDB as the database backend.
