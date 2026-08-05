# Afrigen Beacon v2 — Visual Schemas

Visual companion to `DATABASE_SCHEMA.md`. All diagrams use
[Mermaid](https://mermaid.js.org/) and render natively on GitHub, GitLab,
VS Code, and most Markdown viewers.

> **Source-of-truth note**: these diagrams are derived from
> `beacon_api/models.py`, `beacon_api/urls*.py`, and
> `beacon_project/settings_boolean.py`. If the code changes, update the
> diagrams here in the same PR.

## Table of contents

1. [ER diagram — Option A (literal MongoDB / DBA view)](#1-er-diagram--option-a-literal-mongodb-view)
2. [ER diagram — Option B (domain semantics / researcher view)](#2-er-diagram--option-b-domain-semantics-view)
3. [Runtime topology](#3-runtime-topology)
4. [API endpoint map (Boolean vs Secure)](#4-api-endpoint-map-boolean-vs-secure)
5. [Query lifecycle (request → response)](#5-query-lifecycle-request--response)
6. [Production deployment topology](#6-production-deployment-topology)
7. [Technology stack](#7-technology-stack)

---

## 1. ER diagram — Option A (literal MongoDB view)

Mirrors what's actually stored in Mongo. `VariantInDataset` is shown as a
real collection (which it is — `beacon_api/models.py:176-200`). Use this
when working on queries, indexes, migrations, or data loading.

```mermaid
erDiagram
    VARIANT ||--o{ VARIANT_IN_DATASET : "joined via"
    DATASET ||--o{ VARIANT_IN_DATASET : "joined via"
    INDIVIDUAL ||--o{ VARIANT_IN_DATASET : "joined via"
    VARIANT ||--o{ VARIANT_ANNOTATION : "embeds"
    INDIVIDUAL ||--o{ BIOSAMPLE : "individual_id (string ref)"
    BIOSAMPLE ||--o{ ANALYSIS : "biosample_id (string ref)"
    COHORT }o--o{ INDIVIDUAL : "individual_ids[] (string refs)"

    VARIANT {
        string id PK
        string assembly_id "GRCh38 / GRCh37"
        string reference_name "chromosome"
        int start
        int end
        string reference_bases
        string alternate_bases
        string variant_type "SNP / DEL / INS"
        list dataset_ids "denormalised"
        embedded annotations "VariantAnnotation[]"
        datetime created
        datetime updated
    }

    VARIANT_ANNOTATION {
        string gene_id
        string gene_symbol
        string molecular_consequence
        string clinical_significance
        dict additional_annotations
    }

    INDIVIDUAL {
        string id PK
        string sex
        string ethnicity
        string geographic_origin
        int age
        dict diseases
        dict phenotypic_features
        datetime created
        datetime updated
    }

    DATASET {
        string id PK
        string name
        string description
        string assembly_id
        string dataset_type "default genomics"
        dict dataset_size "variant/sample counts"
        dict contact_info
        datetime create_date
        datetime update_date
    }

    BIOSAMPLE {
        string id PK
        string individual_id FK "string ref to Individual.id"
        string description
        string sample_type
        datetime collection_date
        string tissue
        string sample_processing
        string material_used
        dict additional_properties
    }

    ANALYSIS {
        string id PK
        string biosample_id FK "string ref to Biosample.id"
        string analysis_type
        datetime analysis_date
        string software
        string software_version
        string pipeline_name
        string pipeline_version
        dict analysis_results
    }

    COHORT {
        string id PK
        string name
        string description
        string cohort_type
        int cohort_size
        list individual_ids "string refs"
    }

    VARIANT_IN_DATASET {
        ObjectId variant FK "ReferenceField -> Variant"
        ObjectId dataset FK "ReferenceField -> Dataset"
        ObjectId individual FK "ReferenceField -> Individual"
        string genotype
        float allele_frequency
    }

    FILTERING_TERM {
        string id PK
        string label
        string description
        string ontology "HP / MONDO / HPO"
        string ontology_id
        string term_category
    }

    QUERY_LOG {
        string query_type
        dict query_params
        int response_status
        int response_time_ms
        int hits_count
        string client_ip
        datetime created
    }
```

### Storage notes

- **Embedded vs referenced.** `VariantAnnotation` lives inside each `Variant`
  document (read together; no join cost). `VariantInDataset` is its own
  collection because genotype data is dataset-scoped and large.
- **String IDs vs ReferenceFields.** Most cross-collection links are stored as
  plain string IDs (`Biosample.individual_id`, `Analysis.biosample_id`,
  `Cohort.individual_ids[]`). The only true `mongoengine.ReferenceField` joins
  live in `VariantInDataset`. This is deliberate — string IDs let MongoDB
  serve queries without `$lookup` round-trips.
- **Indexes** (`auto_create_index: False` on all models — created manually in
  deployment scripts):
  - `variants`: assembly_id, reference_name, start, reference_bases,
    alternate_bases
  - `biosamples`: individual_id
  - `analyses`: biosample_id
  - `cohorts`: name
  - `filtering_terms`: ontology, ontology_id
  - `variant_in_dataset`: variant, dataset, individual + unique compound
    `(variant, dataset, individual)`
  - `query_logs`: created, query_type, -created (only collection with
    auto-index)

---

## 2. ER diagram — Option B (domain semantics view)

Collapses the storage detail. Use this when explaining the data model to
researchers, in onboarding, or in papers.

```mermaid
erDiagram
    VARIANT }o--o{ DATASET : "appears in (with allele freq)"
    DATASET }o--o{ INDIVIDUAL : "includes (with genotype)"
    INDIVIDUAL ||--o{ BIOSAMPLE : "provides"
    BIOSAMPLE ||--o{ ANALYSIS : "is analysed by"
    COHORT }o--o{ INDIVIDUAL : "groups"
    VARIANT ||--o{ VARIANT_ANNOTATION : "is annotated with"
    FILTERING_TERM }o--o{ INDIVIDUAL : "filters / classifies"

    VARIANT {
        string id
        string assembly
        string chromosome
        int start_position
        int end_position
        string ref_allele
        string alt_allele
        string type "SNP / INDEL / etc"
    }

    VARIANT_ANNOTATION {
        string gene
        string consequence
        string clinical_significance
    }

    INDIVIDUAL {
        string id
        string sex
        string ethnicity
        string geographic_origin
        list diseases
        list phenotypic_features
    }

    BIOSAMPLE {
        string id
        string tissue
        string sample_type
        date collection_date
    }

    ANALYSIS {
        string id
        string type
        string pipeline
        date date
    }

    DATASET {
        string id
        string name
        string assembly
    }

    COHORT {
        string id
        string name
        int size
    }

    FILTERING_TERM {
        string id
        string label
        string ontology
    }
```

`★ Insight ─────────────────────────────────────`
The two diagrams describe the **same data** but optimise for different
reasoning. Option A answers "where does this field live and how is it
indexed?" Option B answers "what are the entities and how do they relate
scientifically?" Keep both in sync — when you add a new field to `models.py`,
update Option A; when the conceptual model changes (new entity type,
redefined relationship), update Option B.
`─────────────────────────────────────────────────`

---

## 3. Runtime topology

What runs where in production. Replaces the ASCII art in `CLAUDE.md` with
a renderable version.

```mermaid
graph LR
    Client["Browser /<br/>API client"]

    subgraph Edge["Edge layer"]
        Nginx["nginx<br/>TLS termination<br/>rate limit + CORS"]
    end

    subgraph App["Application containers"]
        Frontend["beacon-frontend<br/>Next.js 14<br/>:3000"]
        API["beacon-api-boolean<br/>Django 4.0 + DRF<br/>:8000"]
    end

    subgraph Data["Data layer (internal only)"]
        Mongo[("MongoDB 5.0<br/>:27017")]
        Redis[("Redis 6<br/>:6379")]
    end

    Client -->|HTTPS| Nginx
    Nginx -->|"/ "| Frontend
    Nginx -->|/api/*| API
    Frontend -.->|"server-side render only"| API
    API -->|MongoEngine ODM| Mongo
    API -->|cache + rate-limit counters| Redis

    classDef edge fill:#ffe8cc,stroke:#d97706,color:#000
    classDef app fill:#dbeafe,stroke:#2563eb,color:#000
    classDef data fill:#dcfce7,stroke:#16a34a,color:#000
    class Nginx edge
    class Frontend,API app
    class Mongo,Redis data
```

> The `traefik/` directory in the repo is aspirational — production currently
> runs nginx. See `CLAUDE.md` "Runtime topology" for the rationale.

---

## 4. API endpoint map (Boolean vs Secure)

Shows which routes each mode exposes and highlights the **4 unrouted entry
types** flagged in `docs/SPEC_CONFORMANCE.md`.

```mermaid
graph TD
    classDef boolean fill:#dcfce7,stroke:#16a34a,color:#000
    classDef secure fill:#fee2e2,stroke:#dc2626,color:#000
    classDef both fill:#dbeafe,stroke:#2563eb,color:#000
    classDef unrouted fill:#f3f4f6,stroke:#6b7280,color:#6b7280,stroke-dasharray: 5 5

    Root["/api/"] --> Info["Service info"]
    Root --> Discovery["Discovery"]
    Root --> Query["Query / data"]
    Root --> Catalog["Catalog metadata"]

    Info --> R1["GET /<br/>GET /info<br/>GET /service-info"]:::both
    Info --> R2["GET /configuration<br/>GET /entry_types<br/>GET /map"]:::both
    Info --> R3["GET /health"]:::both

    Query --> Q1["GET/POST /g_variants<br/>GET /g_variants/&lt;id&gt;"]:::both
    Query --> Q2["POST /query/variants<br/>POST /query/individuals"]:::boolean
    Query --> Q3["POST /query"]:::secure

    Catalog --> C1["GET /datasets<br/>GET /datasets/&lt;id&gt;"]:::both
    Catalog --> C2["GET /cohorts<br/>GET /cohorts/&lt;id&gt;"]:::both
    Catalog --> C3["GET /filtering_terms<br/>GET /filtering_terms/&lt;id&gt;"]:::both

    Catalog --> C4["GET /individuals<br/>GET /individuals/&lt;id&gt;"]:::secure
    Catalog --> C5["GET /biosamples<br/>GET /biosamples/&lt;id&gt;"]:::secure
    Catalog --> C6["GET /analyses<br/>GET /analyses/&lt;id&gt;"]:::secure

    Discovery --> D1["Boolean: /individuals,<br/>/biosamples, /analyses, /runs<br/>(empty stubs — verifier passes)"]:::unrouted
    Discovery --> D2["Boolean: /datasets/&lt;id&gt;/&lt;entry_type&gt;<br/>(scoped query stub)"]:::unrouted

    legend1["Both modes"]:::both
    legend2["Boolean only"]:::boolean
    legend3["Secure only"]:::secure
    legend4["Stub / spec-compliance only"]:::unrouted
```

| Mode | URL conf | Auth | Use case |
|---|---|---|---|
| **Boolean** | `beacon_api/urls_boolean.py` | none | Public discovery (yes/no) |
| **Secure** | `beacon_api/urls.py` | JWT / AAI | Authenticated detail access |

---

## 5. Query lifecycle (request → response)

Where rate limiting, caching, and audit logging sit. Reflects the actual
middleware order in `beacon_project/settings_boolean.py:51-63`.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant N as nginx
    participant RM as RateLimitMiddleware
    participant V as View<br/>(views_boolean.py)
    participant R as Redis
    participant M as MongoDB
    participant QL as QueryLogMiddleware

    C->>N: GET /api/g_variants?…
    N->>RM: forward to Django app
    RM->>R: INCR rate_limit:<ip>:<endpoint>
    alt Over limit
        RM-->>C: 429 Too Many Requests
    else Within limit
        RM->>V: pass through
        V->>V: validate input<br/>(validators.py)
        V->>R: GET cache:<query-hash>
        alt Cache hit
            R-->>V: cached response
        else Cache miss
            V->>M: query variants/individuals/…
            M-->>V: documents
            V->>R: SETEX cache:<query-hash> (5 min TTL)
        end
        V-->>RM: JSON response
        RM-->>QL: response object
        QL->>M: insert QueryLog<br/>(best-effort, try/except)
        QL-->>N: response
        N-->>C: 200 OK + JSON
    end
```

### Where to look in code

| Step | File |
|---|---|
| Rate limiting | `beacon_api/middleware.py:13-105` (`RateLimitMiddleware`) |
| Input validation | `beacon_api/validators.py` |
| Boolean view logic | `beacon_api/views_boolean.py` |
| Cache key + TTL | `beacon_project/settings_boolean.py` (`CACHES`); TTL 5 min |
| Audit log write | `beacon_api/middleware.py` (`QueryLogMiddleware`) |
| Audit log model | `beacon_api/models.py:230-245` (`QueryLog`) |

`★ Insight ─────────────────────────────────────`
The middleware order matters: `RateLimitMiddleware` runs **before** the view
(so rejected requests cost zero DB work), and `QueryLogMiddleware` runs
**after** (so it sees the final response status and `numTotalResults`). The
audit write is wrapped in `try/except` — a Mongo blip while logging won't
500 the user-facing response. This is **fail-open by design** for
observability, not security.
`─────────────────────────────────────────────────`

---

## 6. Production deployment topology

Two ILIFU VMs serving different URLs from the same codebase (manual rsync
deploys; CI/CD declared but never validated — see `CLAUDE.md` "CI/CD status").

```mermaid
graph TB
    Users["Users worldwide"]

    subgraph DNS["DNS / Edge"]
        DNS1["beacon.afrigen-d.org<br/>(zone managed externally)"]
        DNS2["api-beacon.afrigen-d.dev<br/>(Cloudflare)"]
        UCT["bantumi.cbio.uct.ac.za<br/>137.158.204.33<br/>(UCT nginx forwarder)"]
        CF["Cloudflare Tunnel<br/>03c0acae-…-579154e80cf1"]
    end

    subgraph VM1["ILIFU VM #1 — afrigend-beacon-prod (192.168.101.151 / FIP 154.114.10.84)"]
        VM1Stack["Full stack<br/>compose: docker-compose-boolean-ssl.yml"]
        VM1A["beacon-nginx"]
        VM1B["beacon-frontend (Next.js)"]
        VM1C["beacon-api-boolean (Django)"]
        VM1D["beacon-mongodb"]
        VM1E["beacon-redis"]
        VM1A --> VM1B
        VM1A --> VM1C
        VM1C --> VM1D
        VM1C --> VM1E
    end

    subgraph VM2["ILIFU VM #2 — afrigend-beacon-network (192.168.101.163)"]
        VM2A["beacon-api (this repo, API only)<br/>/opt/afrigend/beacon/<br/>compose: docker-compose.dev.yml"]
        VM2B["beacon-network-* containers<br/>/opt/afrigend/beacon-network/<br/>(separate repo)"]
        VM2C["mongodb + redis (this repo)"]
        VM2A --> VM2C
    end

    Users -->|HTTPS| DNS1
    Users -->|HTTPS| DNS2
    DNS1 --> UCT
    UCT -->|forward| VM1A
    DNS2 --> CF
    CF -->|tunnel| VM2A

    classDef vm fill:#dbeafe,stroke:#2563eb,color:#000
    classDef edge fill:#ffe8cc,stroke:#d97706,color:#000
    class VM1Stack,VM1A,VM1B,VM1C,VM1D,VM1E,VM2A,VM2B,VM2C vm
    class DNS1,DNS2,UCT,CF edge
```

### Critical operational rules (mirrored from `CLAUDE.md`)

- VM #2 hosts **two unrelated stacks** — this repo's API-only sidecar **and**
  the separate `african-beacon-network` repo. They share the host but not
  the codebase.
- VM #1's working tree at `~/afrigend-beacon2/` has **no `origin` remote**.
  Deploys are manual rsync; `git pull` won't work.
- Until CI/CD is fixed, every deploy goes through the manual steps in
  `CLAUDE.md` "Production Deployment".

---

## 7. Technology stack

Every technology actually used in production, grouped by layer. Versions are
sourced from `requirements.txt`, `frontend/package.json`, `Dockerfile.boolean`,
`frontend/Dockerfile`, and `compose/docker-compose.dev.yml`. See the table
below the diagram for exact versions.

```mermaid
graph TB
    classDef edge fill:#ffe8cc,stroke:#d97706,color:#000
    classDef fe fill:#fef3c7,stroke:#ca8a04,color:#000
    classDef be fill:#dbeafe,stroke:#2563eb,color:#000
    classDef data fill:#dcfce7,stroke:#16a34a,color:#000
    classDef infra fill:#ede9fe,stroke:#7c3aed,color:#000
    classDef test fill:#fce7f3,stroke:#db2777,color:#000
    classDef obs fill:#cffafe,stroke:#0891b2,color:#000

    subgraph EDGE["Edge / network"]
        E1["nginx<br/>(prod TLS + reverse proxy)"]:::edge
        E2["Traefik v3.4<br/>(dev only — file provider)"]:::edge
        E3["Cloudflare Tunnel<br/>(VM #2 → public)"]:::edge
    end

    subgraph FE["Frontend — Next.js app"]
        F1["Next.js 14 (App Router)<br/>React 18 + TypeScript 5"]:::fe
        F2["Tailwind CSS 4<br/>+ Radix Slot, clsx, tailwind-merge, CVA"]:::fe
        F3["TanStack Query<br/>(server state + cache)"]:::fe
        F4["Zustand<br/>(client state)"]:::fe
        F5["react-hook-form + Zod<br/>(forms + validation)"]:::fe
        F6["TanStack Table<br/>(results grid)"]:::fe
        F7["Recharts<br/>(visualisations)"]:::fe
        F8["Axios<br/>(HTTP client)"]:::fe
        F9["Lucide + Heroicons<br/>(icons)"]:::fe
        F10["next-themes<br/>(dark mode)"]:::fe
        F11["react-hot-toast<br/>(notifications)"]:::fe
    end

    subgraph BE["Backend — Django API"]
        B1["Python 3.9-slim"]:::be
        B2["Django 4.0.10"]:::be
        B3["Django REST Framework 3.14<br/>+ drf-spectacular (OpenAPI)"]:::be
        B4["MongoEngine 0.27 ODM<br/>+ django-mongoengine + PyMongo 4.6"]:::be
        B5["djangorestframework-simplejwt<br/>(secure mode auth)"]:::be
        B6["django-cors-headers<br/>+ django-ratelimit"]:::be
        B7["django-redis<br/>(cache backend)"]:::be
        B8["Gunicorn 21<br/>(WSGI server)"]:::be
        B9["WhiteNoise<br/>(static files)"]:::be
        B10["python-decouple, dotenv<br/>(env config)"]:::be
    end

    subgraph DATA["Data layer"]
        D1[("MongoDB 5.0<br/>BSON storage")]:::data
        D2[("Redis 6 (alpine)<br/>cache + rate-limit counters")]:::data
    end

    subgraph INFRA["Infrastructure / build"]
        I1["Docker + Docker Compose"]:::infra
        I2["ILIFU OpenStack VMs<br/>(Ubuntu)"]:::infra
        I3["GitHub Actions<br/>(declared, never validated)"]:::infra
    end

    subgraph TEST["Testing"]
        T1["Playwright (E2E)"]:::test
        T2["Jest + Testing Library<br/>(frontend unit)"]:::test
        T3["Django unittest<br/>(backend)"]:::test
        T4["Locust<br/>(load testing)"]:::test
        T5["beacon-verifier (Rust CLI)<br/>(GA4GH spec conformance)"]:::test
    end

    subgraph OBS["Observability"]
        O1["systemd timer<br/>+ textfile collector"]:::obs
        O2["Prometheus<br/>(scrapes node_exporter)"]:::obs
        O3["Grafana<br/>(dashboard.afrigen-d.dev)"]:::obs
    end

    EDGE -.->|routes traffic to| FE
    EDGE -.->|/api/* to| BE
    FE -->|HTTPS /api/*| BE
    BE -->|MongoEngine| D1
    BE -->|django-redis| D2
    BE -->|writes QueryLog metrics| O1
    O1 --> O2 --> O3
    INFRA -.->|hosts| EDGE
    INFRA -.->|hosts| FE
    INFRA -.->|hosts| BE
    INFRA -.->|hosts| DATA
    TEST -.->|exercises| FE
    TEST -.->|exercises| BE
```

### Versions reference

| Layer | Component | Version | Source |
|---|---|---|---|
| Edge | nginx (prod) | distro pkg | host config |
| Edge | Traefik | v3.4 | `compose/docker-compose.dev.yml` |
| Edge | Cloudflare Tunnel | cloudflared latest | VM #2 systemd |
| FE | Node.js (build/runtime) | 20-alpine | `frontend/Dockerfile` |
| FE | Next.js | 14.2.21 | `frontend/package.json` |
| FE | React | 18.3.1 | `frontend/package.json` |
| FE | TypeScript | 5.x | `frontend/package.json` |
| FE | Tailwind CSS | 4.1.18 | `frontend/package.json` |
| FE | TanStack Query | 5.62.14 | `frontend/package.json` |
| FE | TanStack Table | 8.20.6 | `frontend/package.json` |
| FE | Zustand | 5.0.3 | `frontend/package.json` |
| FE | react-hook-form | 7.54.2 | `frontend/package.json` |
| FE | Zod | 3.24.1 | `frontend/package.json` |
| FE | Axios | 1.7.9 | `frontend/package.json` |
| FE | Recharts | 2.15.0 | `frontend/package.json` |
| BE | Python | 3.9-slim | `Dockerfile.boolean` |
| BE | Django | 4.0.10 | `requirements.txt` |
| BE | DRF | 3.14.0 | `requirements.txt` |
| BE | drf-spectacular | 0.26.5 | `requirements.txt` |
| BE | MongoEngine | 0.27.0 | `requirements.txt` |
| BE | PyMongo | 4.6.1 | `requirements.txt` |
| BE | django-mongoengine | 0.5.4 | `requirements.txt` |
| BE | simplejwt | 5.3.1 | `requirements.txt` |
| BE | django-cors-headers | 4.3.1 | `requirements.txt` |
| BE | django-ratelimit | 4.1.0 | `requirements.txt` |
| BE | django-redis | 5.4.0 | `requirements.txt` |
| BE | redis (Python client) | 5.0.1 | `requirements.txt` |
| BE | Gunicorn | 21.2.0 | `requirements.txt` |
| BE | WhiteNoise | 6.6.0 | `requirements.txt` |
| Data | MongoDB | 5.0 | `compose/docker-compose.dev.yml` |
| Data | Redis | 6-alpine | `compose/docker-compose.dev.yml` |
| Test | Playwright | 1.49.1 | `frontend/package.json` |
| Test | Jest | 29.7.0 | `frontend/package.json` |
| Test | beacon-verifier | latest (Rust) | `docs/SPEC_CONFORMANCE.md` |

### Why these choices

`★ Insight ─────────────────────────────────────`
- **MongoEngine over MongoDB's BSON driver directly** — gives the team
  Django-style declarative models (see `beacon_api/models.py`) at the cost of
  pinning Django to <4.1 (`django-mongoengine` constraint). That pin is the
  reason `requirements.txt` locks `django==4.0.10` despite Django 5.x being
  current.
- **TanStack Query + Zustand split** — server-state (API responses) is owned
  by TanStack Query (caching, revalidation, retries); client-state (form
  drafts, UI toggles) is owned by Zustand. This split is a deliberate choice
  over Redux because the API surface is small enough that Redux's machinery
  is overkill.
- **react-hook-form + Zod** — form schema is defined once in Zod and reused
  for both client validation and TypeScript type inference. The same Zod
  schema validates URL query params (shareable queries) in
  `frontend/src/lib/utils/queryParams.ts`.
- **Two Redis roles, one container** — Redis 6 serves both DRF response
  caching (5-minute TTL) and rate-limit counters (sliding window). Same
  process, different key prefixes (`cache:*` vs `rate_limit:*`).
- **beacon-verifier is the only non-Python/Node tool** — it's a Rust CLI
  from EGA used to validate GA4GH spec conformance. Run via Docker, not
  installed locally. Tracked in `docs/SPEC_CONFORMANCE.md`.
`─────────────────────────────────────────────────`

---

## How to render these diagrams

| Tool | What works |
|---|---|
| GitHub web UI | Renders inline in this Markdown file — no setup needed |
| VS Code | Install "Markdown Preview Mermaid Support" extension |
| CLI export | `npx @mermaid-js/mermaid-cli -i SCHEMA_DIAGRAMS.md -o out.pdf` |
| Live editor | Paste any code block into <https://mermaid.live> for tweaking |

## Keeping these diagrams in sync

Update this file whenever:

1. A new model is added to `beacon_api/models.py` → update Option A +
   Option B ER diagrams.
2. A new URL route is added to either `urls.py` or `urls_boolean.py` → update §4.
3. Middleware is added/reordered in `settings_*.py` → update §5.
4. A deployment target is added/removed → update §6.
5. A dependency is bumped/added/removed in `requirements.txt`,
   `frontend/package.json`, or a Dockerfile → update §7.

A future enhancement would be a CI check that diffs `models.py` against the
diagrams' field lists and fails the PR if they drift — not implemented yet,
but the file structure above is friendly to automation.
