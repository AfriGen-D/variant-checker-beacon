'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { Container } from '@/components/layout/Container';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { beaconApi } from '@/lib/api/beacon';
import type { Dataset } from '@/lib/api/types';
import { Database, Calendar, Dna, Users, Search, X } from 'lucide-react';

const ChromosomeDistribution = dynamic(
  () => import('@/components/charts/ChromosomeDistribution').then(m => ({ default: m.ChromosomeDistribution })),
  { ssr: false }
);

const PAGE_SIZE = 6;

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

type SortKey = 'name' | 'variants' | 'samples' | 'recent';

const SORT_KEYS: ReadonlySet<SortKey> = new Set(['name', 'variants', 'samples', 'recent']);

export default function DatasetsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  // Initialise filter state from URL params so the page is shareable.
  const [query, setQuery] = useState(() => searchParams.get('q') ?? '');
  const [assemblyFilter, setAssemblyFilter] = useState<string>(
    () => searchParams.get('assembly') ?? 'all'
  );
  const [sortKey, setSortKey] = useState<SortKey>(() => {
    const raw = searchParams.get('sort');
    return raw && SORT_KEYS.has(raw as SortKey) ? (raw as SortKey) : 'name';
  });

  useEffect(() => {
    beaconApi.getDatasets()
      .then((res) => setDatasets(res.datasets))
      .catch((err) => setError(err.message || 'Failed to load datasets'))
      .finally(() => setLoading(false));
  }, []);

  // Reset to page 0 whenever filters change
  useEffect(() => {
    setPage(0);
  }, [query, assemblyFilter, sortKey]);

  // Mirror filter state to the URL so links are shareable.
  useEffect(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (assemblyFilter !== 'all') params.set('assembly', assemblyFilter);
    if (sortKey !== 'name') params.set('sort', sortKey);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  // pathname/router are stable refs — only react to filter changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, assemblyFilter, sortKey]);

  // Distinct assembly IDs present in the data, for the filter dropdown
  const assemblies = useMemo(() => {
    const set = new Set<string>();
    datasets.forEach((d) => d.assemblyId && set.add(d.assemblyId));
    return Array.from(set).sort();
  }, [datasets]);

  // Match a single dataset against the search + assembly filter.
  // Search covers id, name, description, and any free-form info metadata.
  const matches = (ds: Dataset): boolean => {
    if (assemblyFilter !== 'all' && ds.assemblyId !== assemblyFilter) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const haystack = [
      ds.id,
      ds.name,
      ds.description ?? '',
      ds.info ? JSON.stringify(ds.info) : '',
    ].join(' ').toLowerCase();
    return haystack.includes(q);
  };

  const filtered = useMemo(() => {
    const list = datasets.filter(matches);
    const cmp = (a: Dataset, b: Dataset) => {
      switch (sortKey) {
        case 'variants':
          return (b.variantCount ?? 0) - (a.variantCount ?? 0);
        case 'samples':
          return (b.sampleCount ?? 0) - (a.sampleCount ?? 0);
        case 'recent':
          return (b.createDateTime ?? '').localeCompare(a.createDateTime ?? '');
        case 'name':
        default:
          return a.name.localeCompare(b.name);
      }
    };
    return [...list].sort(cmp);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasets, query, assemblyFilter, sortKey]);

  const total = datasets.length;
  const filteredTotal = filtered.length;
  const totalPages = Math.ceil(filteredTotal / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalVariants = filtered.reduce((sum, ds) => sum + (ds.variantCount ?? 0), 0);
  const filtersActive = query.trim() !== '' || assemblyFilter !== 'all';

  return (
    <Container className="py-8">
      <div className="mb-6">
        <h1 className="text-4xl font-bold mb-2">Datasets</h1>
        <p className="text-muted-foreground">
          {total === 0
            ? 'Genomic datasets available for variant discovery queries.'
            : filtersActive
              ? `Showing ${filteredTotal} of ${total} dataset${total !== 1 ? 's' : ''} (${totalVariants.toLocaleString()} variants in current view).`
              : `${total} genomic dataset${total !== 1 ? 's' : ''} with ${totalVariants.toLocaleString()} total variants available for discovery.`}
        </p>
      </div>

      {!loading && !error && total > 0 && (
        <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              type="search"
              placeholder="Search by name, ID, or description"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
              aria-label="Search datasets"
            />
          </div>

          {assemblies.length > 1 && (
            <div className="md:w-48">
              <Select
                value={assemblyFilter}
                onChange={(e) => setAssemblyFilter(e.target.value)}
                options={[
                  { value: 'all', label: 'All assemblies' },
                  ...assemblies.map((a) => ({ value: a, label: a })),
                ]}
                aria-label="Filter by assembly"
              />
            </div>
          )}

          <div className="md:w-48">
            <Select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              options={[
                { value: 'name', label: 'Sort: Name (A–Z)' },
                { value: 'variants', label: 'Sort: Most variants' },
                { value: 'samples', label: 'Sort: Most samples' },
                { value: 'recent', label: 'Sort: Newest' },
              ]}
              aria-label="Sort datasets"
            />
          </div>

          {filtersActive && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setQuery('');
                setAssemblyFilter('all');
              }}
              aria-label="Clear search and filters"
            >
              <X className="h-3.5 w-3.5 mr-1" />
              Clear
            </Button>
          )}
        </div>
      )}

      {loading && (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-6 w-2/3 mb-3" />
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <p className="text-destructive font-semibold mb-2">Failed to load datasets</p>
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !error && filteredTotal > 0 && (
        <div className="mb-8">
          <ChromosomeDistribution datasets={filtered} />
        </div>
      )}

      {!loading && !error && filtersActive && filteredTotal === 0 && (
        <Card>
          <CardContent className="pt-6 pb-6 text-center">
            <p className="font-medium mb-1">No datasets match your search.</p>
            <p className="text-sm text-muted-foreground">
              Try a different keyword or clear the filters.
            </p>
          </CardContent>
        </Card>
      )}

      {!loading && !error && filteredTotal > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {paged.map((ds) => (
              <Card key={ds.id} className="flex flex-col">
                <CardContent className="pt-6 flex-1">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Database className="h-5 w-5 text-primary shrink-0" />
                      <h2 className="text-lg font-semibold leading-tight">{ds.name}</h2>
                    </div>
                    {ds.assemblyId && (
                      <Badge variant="info" size="sm">{ds.assemblyId}</Badge>
                    )}
                  </div>

                  {ds.description && (
                    <p className="text-sm text-muted-foreground mb-4 line-clamp-2">{ds.description}</p>
                  )}

                  <div className="flex items-center gap-4 mt-auto pt-3 border-t">
                    {ds.variantCount !== undefined && (
                      <div className="flex items-center gap-1.5 text-sm">
                        <Dna className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-semibold">{ds.variantCount.toLocaleString()}</span>
                        <span className="text-muted-foreground">variants</span>
                      </div>
                    )}
                    {ds.sampleCount !== undefined && (
                      <div className="flex items-center gap-1.5 text-sm">
                        <Users className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-semibold">{ds.sampleCount.toLocaleString()}</span>
                        <span className="text-muted-foreground">samples</span>
                      </div>
                    )}
                    {ds.createDateTime && (
                      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5" />
                        {formatDate(ds.createDateTime)}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-6">
              <p className="text-xs text-muted-foreground">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filteredTotal)} of {filteredTotal}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </Container>
  );
}
