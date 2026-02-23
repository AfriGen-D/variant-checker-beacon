# Beacon API

This directory contains the core implementation of the GA4GH Beacon v2 API using MongoEngine for MongoDB integration.

## Directory Structure

- **fixtures/**: JSON fixture files containing sample data for testing and development.
  - Contains sample datasets, individuals, variants, biosamples, etc.
  - Includes MongoDB-specific fixture format for MongoEngine models

- **management/**: Django management commands for administrative tasks.
  - Custom commands for data loading, indexing, and maintenance.

- **migrations/**: Not actively used with MongoEngine since schema changes are handled differently.

- **models.py**: MongoEngine document definitions that represent the Beacon data model.
  - Defines the MongoDB document schemas for all Beacon objects.
  - Implements proper indexing for optimal query performance.

- **serializers.py**: Django REST Framework serializers for MongoEngine documents.
  - Handles conversion between Python objects and JSON.
  - Implements validation logic for API requests.

- **views.py**: Django views that implement the API endpoints.
  - Handles HTTP requests and produces responses.
  - Implements filtering and query logic using MongoEngine queries.

## Key Files

- **admin.py**: Django admin interface configuration.
- **apps.py**: Django application configuration.
- **urls.py**: URL routing definitions for API endpoints.
- **tests.py**: Unit and integration tests.

## MongoDB Integration

This implementation uses MongoEngine as the Object-Document Mapper (ODM) for MongoDB:

1. **Document-Based Models**: Models are defined as MongoEngine Documents rather than Django Models.
2. **Embedded Documents**: Uses embedded documents for efficient representation of nested data.
3. **Custom Serialization**: Custom `MongoSerializer` class handles conversion of MongoEngine documents to JSON.
4. **Native MongoDB Queries**: Leverages MongoEngine's query syntax for efficient MongoDB queries.
