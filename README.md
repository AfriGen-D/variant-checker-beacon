# GA4GH Beacon v2 API Implementation

**Production-ready genomic data discovery service implementing the GA4GH Beacon v2 specification**

[![GA4GH Beacon v2](https://img.shields.io/badge/GA4GH-Beacon%20v2-blue)](https://beacon-project.io/)
[![Django](https://img.shields.io/badge/Django-4.0.10-green)](https://www.djangoproject.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-5.0-green)](https://www.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue)](https://www.docker.com/)

## Overview

This repository contains a production implementation of the [GA4GH Beacon v2 specification](https://beacon-project.io/) for genomic data discovery. The implementation is **100% compliant** with the official specification and supports both public discovery (Boolean mode) and authenticated access (Secure mode).

**Production Deployment**: Hosted on ILIFU infrastructure

## Features

- ✅ **GA4GH Beacon v2 Compliant** - All required endpoints implemented
- ✅ **Two Deployment Modes** - Boolean (public) and Secure (authenticated)
- ✅ **MongoDB Backend** - Scalable document storage with MongoEngine ODM
- ✅ **Redis Caching** - High-performance query caching
- ✅ **Rate Limiting** - Protection against abuse
- ✅ **Docker Deployment** - Production-ready containers
- ✅ **OpenAPI Documentation** - Interactive API docs with Swagger/ReDoc
- ✅ **Data Tools Suite** - VCF transformation, import/export utilities

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OR Python 3.12+ with MongoDB and Redis

### Deploy with Docker (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd afrigen-beacon-v2

# Deploy Boolean mode (public discovery)
docker-compose -f docker-compose-boolean.yml up -d

# Access API
curl http://localhost:8000/api/

# View documentation
open http://localhost:8000/api/redoc/
```

### Deploy Locally

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start services (MongoDB and Redis must be running)
./run.sh
```

## API Endpoints

### Core Endpoints

```
GET  /api/                    # Beacon info
GET  /api/service-info        # GA4GH service info
GET  /api/configuration       # Configuration
GET  /api/health             # Health check
```

### Data Discovery

```
GET/POST /api/g_variants      # Genomic variants
GET/POST /api/individuals     # Individuals
GET/POST /api/biosamples      # Biosamples
GET/POST /api/datasets        # Datasets
GET/POST /api/cohorts         # Cohorts
GET/POST /api/analyses        # Analyses
```

### Example Query

```bash
# Boolean mode - returns YES/NO
curl "http://localhost:8000/api/g_variants?\
assemblyId=GRCh38&\
referenceName=1&\
start=100000&\
referenceBases=A&\
alternateBases=T"

# Response: {"exists": true}
```

## Deployment Modes

### Boolean Mode (Public)

Public genomic discovery returning only YES/NO responses. No authentication required.

**Use Case**: Public data discovery, privacy-preserving queries

```bash
docker-compose -f docker-compose-boolean.yml up -d
```

### Secure Mode (Authenticated)

Full access to detailed genomic data with JWT authentication and role-based access control.

**Use Case**: Research collaborations, authorized data access

```bash
docker-compose up -d
```

## Data Management

### Transform VCF to Beacon Format

```bash
cd afrigend-beacon2-tools
python vcf_transform/vcf_to_beacon.py input.vcf.gz --output variants.json
```

### Import Data to MongoDB

```bash
python data_import/import_to_mongo.py variants.json --collection variants
```

### Load Sample Data

```bash
python scripts/load_mongo_data.py
```

## Technology Stack

- **Backend**: Django 4.0 + Django REST Framework
- **Database**: MongoDB 5.0 with MongoEngine ODM
- **Cache**: Redis 6
- **API Docs**: DRF Spectacular (OpenAPI 3.0)
- **Deployment**: Docker + Docker Compose
- **Authentication**: JWT with GA4GH AAI integration
- **Web Server**: Nginx with SSL/TLS

## Project Structure

```
afrigen-beacon-v2/
├── beacon_api/              # Core API implementation
│   ├── models.py           # MongoEngine models
│   ├── views.py            # Full API views
│   ├── views_boolean.py    # Boolean-only views
│   ├── serializers.py      # DRF serializers
│   ├── validators.py       # Input validation
│   └── middleware.py       # Rate limiting
├── beacon_project/         # Django project configuration
│   ├── settings.py         # Base settings
│   ├── settings_boolean.py # Boolean mode settings
│   └── settings_secure.py  # Secure mode settings
├── afrigend-beacon2-tools/ # Data management tools
│   ├── vcf_transform/      # VCF conversion
│   ├── data_import/        # Bulk import
│   ├── data_export/        # Export utilities
│   └── validation/         # JSON validation
├── scripts/                # Deployment scripts
├── docker-compose-boolean.yml
├── docker-compose.yml
└── README.md
```

## Documentation

All documentation lives in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [API Reference](docs/API_REFERENCE.md) | Complete API endpoint documentation |
| [Boolean Mode](docs/BOOLEAN_MODE.md) | Public discovery mode guide |
| [Database Schema](docs/DATABASE_SCHEMA.md) | MongoDB collections and indexes |
| [GA4GH AAI Plan](docs/GA4GH_AAI_IMPLEMENTATION_PLAN.md) | Authentication roadmap |
| [ILIFU Data Loading](docs/ILIFU_DATA_LOADING_GUIDE.md) | Production data loading guide |
| [Project Overview](docs/PROJECT_OVERVIEW.md) | Architecture and design decisions |
| [Security Implementation](docs/SECURITY_IMPLEMENTATION.md) | Security architecture details |
| [Testing](docs/TESTING.md) | Test infrastructure, query examples, CI/CD |

**Interactive API docs** (when running locally):
- ReDoc: http://localhost:8000/api/redoc/
- Swagger: http://localhost:8000/api/docs/
- OpenAPI Schema: http://localhost:8000/api/schema/

## Testing

See [docs/TESTING.md](docs/TESTING.md) for full testing documentation.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=beacon_api --cov-report=html
```

## Configuration

### Boolean Mode

```bash
# .env.boolean
DJANGO_DEBUG=False
MONGODB_HOST=mongodb
REDIS_HOST=redis
BEACON_RESPONSE_MODE=BOOLEAN
RATELIMIT_QUERY_ENDPOINT=50/hour
```

### Secure Mode

```bash
# .env.production
DJANGO_DEBUG=False
MONGODB_USERNAME=beacon_admin
MONGODB_PASSWORD=<secure-password>
JWT_SECRET_KEY=<jwt-secret>
GA4GH_AAI_ENABLED=True
```

## Development

See [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) for detailed development instructions, including:
- Architecture overview
- Code patterns
- Adding new endpoints
- Security testing procedures
- Troubleshooting guides

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

[Add license information]

## Contact

**Organization**: AfriGEND 
**Project**: GA4GH Beacon v2 Implementation 
**Production**: beacon2.h3abionet.org-ilifu 

## Acknowledgments

- [GA4GH Beacon Project](https://beacon-project.io/) 
- [H3Africa Bioinformatics Network](https://h3abionet.org/) 
- ILIFU (Ilifu Data Intensive Research Cloud) 
