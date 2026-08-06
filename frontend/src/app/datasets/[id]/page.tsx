'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { Container } from '@/components/layout/Container';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { beaconApi } from '@/lib/api/beacon';
import type { Dataset } from '@/lib/api/types';
import { ArrowLeft, Database, Calendar, Dna, Tag, ExternalLink, Users, Search } from 'lucide-react';

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

export default function DatasetDetailPage({ params }: { params: Promise<{ id: string }> }) {
  // Next 15 made route params a Promise, including in client components,
  // which cannot be async — React's use() unwraps it.
  const { id } = use(params);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    beaconApi.getDatasets()
      .then((res) => {
        const found = res.datasets.find(ds => ds.id === id);
        setDataset(found ?? null);
      })
      .catch((err) => setError(err.message || 'Failed to load dataset'))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <Container className="py-8">
      <Link
        href="/datasets"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to Datasets
      </Link>

      {loading && (
        <div className="space-y-6">
          <Skeleton className="h-10 w-1/3" />
          <div className="grid gap-6 md:grid-cols-2">
            {[1, 2].map(i => (
              <Card key={i}>
                <CardContent className="pt-6">
                  <Skeleton className="h-5 w-1/4 mb-3" />
                  <Skeleton className="h-4 w-2/3" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {error && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <p className="text-destructive font-semibold mb-2">Failed to load dataset</p>
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !error && !dataset && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground py-8">
              Dataset &quot;{id}&quot; not found.
            </p>
          </CardContent>
        </Card>
      )}

      {dataset && (
        <>
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <h1 className="text-4xl font-bold">{dataset.name}</h1>
            <Link href={`/?assemblyId=${encodeURIComponent(dataset.assemblyId ?? 'GRCh38')}`}>
              <Button>
                <Search className="h-4 w-4 mr-2" />
                Query this dataset
              </Button>
            </Link>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">Overview</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <dl className="space-y-3">
                  {dataset.description && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Description</dt>
                      <dd className="text-sm mt-0.5">{dataset.description}</dd>
                    </div>
                  )}
                  {dataset.assemblyId && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Assembly</dt>
                      <dd className="mt-0.5">
                        <Badge variant="info" size="sm">{dataset.assemblyId}</Badge>
                      </dd>
                    </div>
                  )}
                  {dataset.variantCount !== undefined && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Variant Count</dt>
                      <dd className="text-sm mt-0.5 flex items-center gap-1.5">
                        <Dna className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-semibold">{dataset.variantCount.toLocaleString()}</span>
                      </dd>
                    </div>
                  )}
                  {dataset.sampleCount !== undefined && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Samples</dt>
                      <dd className="text-sm mt-0.5 flex items-center gap-1.5">
                        <Users className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-semibold">{dataset.sampleCount.toLocaleString()}</span>
                      </dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Tag className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">Metadata</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <dl className="space-y-3">
                  {dataset.version && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Version</dt>
                      <dd className="text-sm mt-0.5">{dataset.version}</dd>
                    </div>
                  )}
                  {dataset.createDateTime && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Created</dt>
                      <dd className="text-sm mt-0.5 flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        {formatDate(dataset.createDateTime)}
                      </dd>
                    </div>
                  )}
                  {dataset.updateDateTime && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Last Updated</dt>
                      <dd className="text-sm mt-0.5 flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        {formatDate(dataset.updateDateTime)}
                      </dd>
                    </div>
                  )}
                  {dataset.externalUrl && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">External URL</dt>
                      <dd className="text-sm mt-0.5">
                        <a
                          href={dataset.externalUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline inline-flex items-center gap-1"
                        >
                          {dataset.externalUrl}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </Container>
  );
}
