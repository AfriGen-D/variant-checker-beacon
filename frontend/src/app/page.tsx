'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useVariantQuery } from '@/lib/hooks/useBeaconQuery';
import { useQueryStore } from '@/lib/store/queryStore';
import { Container } from '@/components/layout/Container';
import { QueryConsole } from '@/components/query/QueryConsole';
import { DatasetResults } from '@/components/results/DatasetResults';
import { Card, CardContent } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import type { VariantQuery, Dataset } from '@/lib/api/types';
import type { VariantQueryFormData } from '@/lib/utils/validators';
import type { QueryMode } from '@/lib/utils/constants';
import { queryFromSearchParams, searchParamsFromQuery } from '@/lib/utils/queryParams';
import toast from 'react-hot-toast';
import { getErrorMessage, isRateLimitError } from '@/lib/api/client';
import { beaconApi } from '@/lib/api/beacon';

function HomePageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  // Parse initial query (+ mode) from URL params
  const initialParsed = useRef(queryFromSearchParams(searchParams));
  const [mode, setMode] = useState<QueryMode>(initialParsed.current?.mode ?? 'variant');
  const [submittedQuery, setSubmittedQuery] = useState<VariantQuery | null>(null);
  const [filters, setFilters] = useState<string[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([]);
  const { addQuery } = useQueryStore();

  const autoSubmitted = useRef(false);

  useEffect(() => {
    beaconApi
      .getDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(err => {
        console.error('Failed to load datasets:', err);
        toast.error('Could not load available datasets');
      });
  }, []);

  const { data, isLoading, error } = useVariantQuery(
    submittedQuery as VariantQuery,
    !!submittedQuery
  );

  const handleSubmit = (query: VariantQuery, submittedMode: QueryMode) => {
    setMode(submittedMode);
    setSubmittedQuery(query);
    // Update URL without scroll or history entry
    router.replace(`/?${searchParamsFromQuery(query, submittedMode)}`, { scroll: false });
    toast.success('Query submitted');
  };

  // Auto-submit on mount if URL has valid params
  useEffect(() => {
    const parsed = initialParsed.current;
    if (parsed && !autoSubmitted.current) {
      autoSubmitted.current = true;
      const data = parsed.variant ?? parsed.region;
      if (data) {
        handleSubmit(
          {
            assemblyId: data.assemblyId,
            referenceName: data.referenceName,
            start: data.start,
            end: data.end,
            referenceBases: (data as VariantQueryFormData).referenceBases,
            alternateBases: (data as VariantQueryFormData).alternateBases,
          },
          parsed.mode
        );
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lastSavedRef = useRef<string | null>(null);

  useEffect(() => {
    if (data && submittedQuery) {
      const key = JSON.stringify(submittedQuery);
      if (lastSavedRef.current !== key) {
        lastSavedRef.current = key;
        addQuery(submittedQuery, data);
      }
    }
  }, [data, submittedQuery, addQuery]);

  useEffect(() => {
    if (error) {
      if (isRateLimitError(error)) {
        toast.error('Rate limit exceeded. Please try again later.');
      } else {
        toast.error(getErrorMessage(error));
      }
    }
  }, [error]);

  return (
    <Container className="py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Variant checker</h1>
        <p className="text-lg text-muted-foreground mt-2 max-w-2xl">
          Look up any genomic variant across African reference panels, then jump straight to
          allele frequencies, annotations and clinical detail in the major public databases.
        </p>
      </div>

      <div className="space-y-6">
        <QueryConsole
          mode={mode}
          onModeChange={setMode}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          filters={filters}
          onFiltersChange={setFilters}
          datasets={datasets}
          selectedDatasetIds={selectedDatasetIds}
          onSelectedDatasetsChange={setSelectedDatasetIds}
          initialVariant={initialParsed.current?.variant ?? null}
          initialRegion={initialParsed.current?.region ?? null}
        />

        {isLoading && (
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <Skeleton className="h-8 w-1/3" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            </CardContent>
          </Card>
        )}

        {error && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-8">
                <p className="text-destructive font-semibold mb-2">Query Failed</p>
                <p className="text-sm text-muted-foreground">{getErrorMessage(error)}</p>
              </div>
            </CardContent>
          </Card>
        )}

        <DatasetResults
          datasetAlleleResponses={data?.response?.datasetAlleleResponses}
          datasets={datasets}
          query={submittedQuery}
          selectedDatasetIds={selectedDatasetIds}
          rawResponse={data}
          beaconHandovers={data?.response?.beaconHandovers}
          status={
            isLoading ? 'loading' : error ? 'error' : submittedQuery ? 'success' : 'idle'
          }
        />
      </div>
    </Container>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={
      <Container className="py-8">
        <Skeleton className="h-10 w-1/3 mb-8" />
        <Skeleton className="h-64 w-full" />
      </Container>
    }>
      <HomePageInner />
    </Suspense>
  );
}
