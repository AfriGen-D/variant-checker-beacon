'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { Container } from '@/components/layout/Container';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { beaconApi } from '@/lib/api/beacon';
import type { Dataset } from '@/lib/api/types';
import { Database, Calendar, Dna, Users } from 'lucide-react';

const ChromosomeDistribution = dynamic(
  () => import('@/components/charts/ChromosomeDistribution').then(m => ({ default: m.ChromosomeDistribution })),
  { ssr: false }
);

const PAGE_SIZE = 6;

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    beaconApi.getDatasets()
      .then((res) => setDatasets(res.datasets))
      .catch((err) => setError(err.message || 'Failed to load datasets'))
      .finally(() => setLoading(false));
  }, []);

  const total = datasets.length;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const paged = datasets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalVariants = datasets.reduce((sum, ds) => sum + (ds.variantCount ?? 0), 0);

  return (
    <Container className="py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Datasets</h1>
        <p className="text-muted-foreground">
          {total > 0
            ? `${total} genomic dataset${total !== 1 ? 's' : ''} with ${totalVariants.toLocaleString()} total variants available for discovery.`
            : 'Genomic datasets available for variant discovery queries.'}
        </p>
      </div>

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

      {!loading && !error && datasets.length > 0 && (
        <div className="mb-8">
          <ChromosomeDistribution datasets={datasets} />
        </div>
      )}

      {!loading && !error && (
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
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
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
