# GA4GH Beacon v2 - Frontend

Next.js + TypeScript frontend for the GA4GH Beacon v2 API.

## ✅ Status: Production Ready

All phases complete! The frontend includes:
- ✅ Complete query interface with form validation
- ✅ Boolean mode results display (YES/NO)
- ✅ Query history with localStorage persistence
- ✅ Responsive design (mobile + desktop)
- ✅ Error handling and rate limit detection
- ✅ Toast notifications for user feedback
- ✅ Type-safe API integration

## Quick Start

### Local Development

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local

# Edit .env.local to point to your backend
# NEXT_PUBLIC_BEACON_API_URL=http://localhost:8000

# Start development server
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000).

**Backend API**: Make sure the Beacon v2 API is running at `http://localhost:8000`.

### Docker Deployment

```bash
# From project root
docker compose -f compose/docker-compose-frontend.yml up -d

# Or build manually
cd frontend
docker build -t beacon-frontend -f docker/Dockerfile \
  --build-arg NEXT_PUBLIC_BEACON_API_URL=http://localhost:8000 .
docker run -p 3000:3000 beacon-frontend
```

## Project Structure

```
frontend/
├── src/
│   ├── app/                      # Next.js App Router pages
│   │   ├── layout.tsx           # Root layout with Header/Footer
│   │   ├── page.tsx             # Home page
│   │   ├── query/page.tsx       # Query interface (MAIN)
│   │   ├── about/page.tsx       # About page
│   │   ├── docs/page.tsx        # API docs
│   │   ├── loading.tsx          # Loading state
│   │   ├── error.tsx            # Error boundary
│   │   └── not-found.tsx        # 404 page
│   ├── components/
│   │   ├── ui/                  # Base UI components
│   │   │   ├── Button.tsx       # Reusable button
│   │   │   ├── Input.tsx        # Form input with validation
│   │   │   ├── Select.tsx       # Dropdown select
│   │   │   ├── Card.tsx         # Card container
│   │   │   └── Badge.tsx        # Status badge
│   │   ├── layout/              # Layout components
│   │   │   ├── Header.tsx       # Navigation header
│   │   │   ├── Footer.tsx       # Page footer
│   │   │   └── Container.tsx    # Content container
│   │   ├── query/               # Query components
│   │   │   └── VariantQueryForm.tsx  # Main query form
│   │   ├── results/             # Results components
│   │   │   ├── ExistsIndicator.tsx   # YES/NO display
│   │   │   ├── ResultsSummary.tsx    # Query metadata
│   │   │   └── QueryHistory.tsx      # Recent queries
│   │   └── Providers.tsx        # React Query + Toast provider
│   ├── lib/
│   │   ├── api/                 # API client
│   │   │   ├── client.ts        # Axios instance + interceptors
│   │   │   ├── beacon.ts        # All Beacon API functions
│   │   │   └── types.ts         # TypeScript interfaces
│   │   ├── hooks/               # Custom hooks
│   │   │   ├── useBeaconQuery.ts    # React Query hooks
│   │   │   └── useDebounce.ts       # Debounce hook
│   │   ├── store/               # Zustand stores
│   │   │   └── queryStore.ts    # Query history store
│   │   └── utils/               # Utilities
│   │       ├── constants.ts     # Assemblies, chromosomes, bases
│   │       ├── formatters.ts    # Data formatting
│   │       └── validators.ts    # Zod schemas
│   └── types/                   # Global types
├── public/                      # Static assets
├── docker/                      # Docker config
│   ├── Dockerfile              # Multi-stage build
│   └── nginx.conf              # Nginx config (optional)
└── __tests__/                  # Tests (future)
```

## Features

### Query Interface

**Form Fields**:
- **Assembly**: GRCh37 or GRCh38
- **Chromosome**: 1-22, X, Y, MT
- **Start Position**: 0-based genomic coordinate (required)
- **End Position**: Optional end coordinate
- **Reference Bases**: Nucleotides (A, T, G, C, N)
- **Alternate Bases**: Nucleotides (A, T, G, C, N)

**Validation**:
- Real-time form validation with Zod
- Comprehensive error messages
- Position range validation (0 to 3 billion)
- Chromosome validation
- Base sequence validation (only ATGCN allowed)

**Results Display**:
- Large YES/NO indicator with color coding
- Query summary with formatted variant notation
- Beacon metadata (API version, timestamp, beacon ID)
- Query history sidebar (last 10 queries)

**Error Handling**:
- Rate limit detection (429 errors)
- Validation error display
- Network error handling
- Toast notifications for all events

### State Management

- **React Query**: Server state with 5-minute cache (matches backend)
- **Zustand**: Client state + localStorage persistence for query history
- **React Hook Form**: Form state management

### Responsive Design

- **Mobile**: Single column layout, touch-friendly
- **Tablet**: 2-column layout
- **Desktop**: 3-column layout with sidebar

## Available Scripts

- `npm run dev` - Start development server (port 3000)
- `npm run build` - Build for production (standalone output)
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run format` - Format code with Prettier
- `npm run type-check` - Run TypeScript type checking
- `npm test` - Run unit tests (watch mode)
- `npm run test:ci` - Run unit tests (CI mode)
- `npm run test:e2e` - Run E2E tests with Playwright

## Environment Variables

Create a `.env.local` file based on `.env.local.example`:

```bash
# API endpoint (required)
NEXT_PUBLIC_BEACON_API_URL=http://localhost:8000
```

**For Docker/production**, also set:
```bash
BACKEND_API_URL=http://beacon-api:8000  # Internal Docker network
```

## Development Workflow

### 1. Start Backend API

```bash
cd /path/to/afrigen-beacon-v2
docker-compose -f docker-compose-boolean.yml up -d
```

Verify backend is running:
```bash
curl http://localhost:8000/api/health
# Should return: {"status": "healthy"}
```

### 2. Start Frontend

```bash
cd frontend
npm run dev
```

### 3. Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api
- **API Docs**: http://localhost:8000/api/redoc

### 4. Test Query

1. Navigate to http://localhost:3000/query
2. Fill in the form:
   - Assembly: GRCh38
   - Chromosome: 1
   - Start Position: 100000
   - Reference Bases: A
   - Alternate Bases: T
3. Click "Query Beacon"
4. See YES/NO result

## Docker Build

### Development Build

```bash
docker build -t beacon-frontend:dev -f docker/Dockerfile \
  --build-arg NEXT_PUBLIC_BEACON_API_URL=http://localhost:8000 \
  .
```

### Production Build

```bash
docker build -t beacon-frontend:latest -f docker/Dockerfile \
  --build-arg NEXT_PUBLIC_BEACON_API_URL=http://beacon2.h3abionet.org-ilifu:8000 \
  .
```

### Run Container

```bash
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_BEACON_API_URL=http://localhost:8000 \
  -e BACKEND_API_URL=http://host.docker.internal:8000 \
  beacon-frontend:latest
```

## Technology Stack

- **Framework**: Next.js 14.2 with App Router
- **Language**: TypeScript 5+
- **Styling**: Tailwind CSS 3.4
- **State Management**:
  - TanStack Query v5 (server state, caching)
  - Zustand (client state, persistence)
- **Forms**: React Hook Form + Zod validation
- **HTTP Client**: Axios with interceptors
- **UI Components**: Custom components with Tailwind
- **Notifications**: React Hot Toast
- **Build**: Next.js standalone output (optimized for Docker)

## API Integration

The frontend integrates with all GA4GH Beacon v2 endpoints:

- `GET /api/` - Beacon info
- `GET /api/health` - Health check
- `GET /api/g_variants` - Query variants
- `GET /api/individuals` - Query individuals
- `GET /api/biosamples` - Query biosamples
- `GET /api/datasets` - Query datasets
- `GET /api/cohorts` - Query cohorts
- `GET /api/filtering_terms` - Get filtering terms

All API calls are type-safe with comprehensive TypeScript interfaces.

## Build Output

```
Route (app)                              Size     First Load JS
┌ ○ /                                    178 B          96.2 kB
├ ○ /_not-found                          150 B          87.4 kB
├ ○ /about                               150 B          87.4 kB
├ ○ /docs                                150 B          87.4 kB
└ ○ /query                               51.6 kB         149 kB
+ First Load JS shared by all            87.3 kB
```

**Total**: 30 TypeScript files created
- Query page: 149 KB (includes form, validation, results, history)
- Other pages: ~87 KB each
- All pages prerendered as static content

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### Backend API Not Reachable

```bash
# Check backend is running
docker ps | grep beacon

# Check backend logs
docker logs beacon-api

# Test API directly
curl http://localhost:8000/api/health
```

### Build Errors

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

## Future Enhancements

### Phase 2: Secure Mode Support
- JWT authentication
- Login/logout UI
- Protected routes
- Full variant data display
- Variant details table

### Phase 3: Advanced Features
- Bulk query upload (CSV)
- Query result export (CSV/JSON)
- Advanced filtering
- Genomic visualization charts
- Saved queries/bookmarks
- Dark mode

### Phase 4: Testing
- Unit tests with Jest
- E2E tests with Playwright
- Visual regression testing
- Performance testing

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Run `npm run lint` and `npm run type-check`
4. Submit a pull request

## License

[Add license information]

## Contact

**Project**: GA4GH Beacon v2 Implementation
**Organization**: AfriGEN
**Production**: beacon2.h3abionet.org-ilifu
