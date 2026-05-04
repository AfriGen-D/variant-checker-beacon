# AfriGen-D Beacon v2 — API + UI

**Production genomic data discovery service implementing the GA4GH Beacon v2 specification.**

[![GA4GH Beacon v2](https://img.shields.io/badge/GA4GH-Beacon%20v2-blue)](https://beacon-project.io/)
[![Django](https://img.shields.io/badge/Django-4.0.10-green)](https://www.djangoproject.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-5.0-green)](https://www.mongodb.com/)
[![Conformance](https://img.shields.io/badge/EGA%20verifier-17%2F17-brightgreen)](docs/SPEC_CONFORMANCE.md)

## What's in this repo

This is a **monorepo** containing both the API (server) and the UI (web client), plus
data-loading tools and infra config. They live in sibling directories and are deployed
as separate containers behind one reverse proxy.

| Path | Role | Stack | Production URL |
|------|------|-------|----------------|
| **`beacon_api/`** + **`beacon_project/`** | **Backend API** — Beacon v2 endpoints (`/api/g_variants`, `/api/datasets`, …) | Django 4.0 + DRF + MongoEngine | `https://api-beacon.afrigen-d.dev/api/` |
| **`frontend/`** | **Web UI** — query form, results table, datasets browser | Next.js 14 (App Router) + TypeScript + Tailwind | `https://beacon.afrigen-d.org/` |
| **`afrigend-beacon2-tools/`** | Data-loading toolkit — VCF→Beacon transformer, phenotype loader, MongoDB import/export | Python | (offline) |
| **`compose/`** | Docker Compose stacks for dev / prod / frontend-only | YAML | — |
| **`nginx/`** | Production reverse proxy config (the proxy actually serving prod today) | nginx | — |
| **`scripts/`** | Deploy / monitor / data-load operational scripts | Bash + Python | — |
| **`nextflow/`** | Optional pipeline for bulk data ingestion at scale | Nextflow | — |
| **`docs/`** | API reference, conformance results, security docs | Markdown | — |

**Data layer** (containerised, internal only): MongoDB 5.0 (genomic data, indexed by
chromosome/position) + Redis 6 (response cache, rate-limit counters).

> The API and UI are deployed at **different subdomains** today — `api-beacon.afrigen-d.dev`
> serves the API, `beacon.afrigen-d.org` serves the UI. The UI calls the API at runtime
> via the relative `/api/...` path, which the reverse proxy routes to the API container.

## Runtime architecture

```
┌────────────────────────────────────────────────────────────┐
│  nginx (production reverse proxy, TLS termination)         │
│  - /        → frontend container :3000                     │
│  - /api/*   → beacon_api container :8000                   │
└────┬───────────────────────────────────┬───────────────────┘
     │                                   │
     ▼                                   ▼
┌──────────────────┐              ┌──────────────────────────┐
│ frontend         │              │ beacon_api (Django/DRF)  │
│ Next.js 14       │  ── /api ──> │ - views_boolean.py       │
│ - Query form     │              │ - urls_boolean.py        │
│ - Results UI     │              │ - utils.py (envelopes)   │
│ Container :3000  │              │ Container :8000          │
└──────────────────┘              └──────┬───────────────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                          ┌─────────┐         ┌─────────┐
                          │ MongoDB │         │  Redis  │
                          │  :27017 │         │  :6379  │
                          └─────────┘         └─────────┘
```

**Production status:** ILIFU infrastructure, host `afrigend-beacon-network` (192.168.101.163).
**Spec conformance:** ✅ 17/17 EGA `beacon-verifier` checks pass — see [`docs/SPEC_CONFORMANCE.md`](docs/SPEC_CONFORMANCE.md).

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

### Deploy with Docker (recommended)

The default deploy is **full stack** — API + frontend + MongoDB + Redis behind
nginx with TLS termination.

```bash
# Clone repository
git clone git@github.com:mamanambiya/afrigen-beacon-v2.git
cd afrigen-beacon-v2

# Copy and edit env file (set DJANGO_SECRET_KEY, etc.)
cp .env.example .env.boolean

# Build and start the full stack (API + frontend + nginx)
docker compose -f compose/docker-compose-boolean-ssl.yml up -d --build

# Access the UI
open http://localhost/

# Access the API directly
curl http://localhost/api/
```

#### Deployment shapes

| Shape | Compose file | When to use |
|---|---|---|
| **Full stack** (default) | `compose/docker-compose-boolean-ssl.yml` | Public discovery with web UI |
| **Dev (no SSL)** | `compose/docker-compose.dev.yml` | Local development with Traefik dashboard |
| **Frontend only** | `compose/docker-compose-frontend.yml` | Run UI against a remote API |
| **API-only** | bring your own override | Federation node, programmatic-only access (e.g. via Cloudflared tunnel — see the ARDI deployment for a worked example: drop `beacon-frontend` and `nginx`, add `cloudflared`) |

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
docker compose -f compose/docker-compose-boolean-ssl.yml up -d
```

### Secure Mode (Authenticated)

Full access to detailed genomic data with JWT authentication and role-based access control.

**Use Case**: Research collaborations, authorized data access

```bash
docker compose -f compose/docker-compose.prod.yml up -d
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
├── compose/                # Docker Compose files
│   ├── docker-compose-boolean-ssl.yml  # Production: API + UI + nginx + SSL
│   ├── docker-compose.dev.yml          # Local dev with Traefik
│   ├── docker-compose.prod.yml         # Secure mode (authenticated)
│   └── docker-compose-frontend.yml     # Frontend only
├── frontend/               # Next.js 14 web UI
├── nginx/                  # Production reverse proxy config
├── scripts/                # Deployment scripts
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

**Organization**: [AfriGEN-D](https://afrigen-d.org/)
**Email**: support@bioinformaticsinstitute.africa
**Project**: GA4GH Beacon v2 Implementation
**Production**: beacon2.h3abionet.org-ilifu

## Acknowledgments

- [AfriGEN-D](https://afrigen-d.org/)
- [GA4GH Beacon Project](https://beacon-project.io/)
- [H3Africa Bioinformatics Network](https://h3abionet.org/)
- [ILIFU Data Intensive Research Cloud](https://www.ilifu.ac.za/)
