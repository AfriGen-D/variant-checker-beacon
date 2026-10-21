'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDatasetDate } from '@/lib/utils/datasetStats';
import { formatNumber } from '@/lib/utils/formatters';
import type { Dataset } from '@/lib/api/types';
import type { DatasetsStatus } from '@/components/dashboard/DatasetStats';

interface DatasetRailProps {
  datasets: Dataset[];
  status: DatasetsStatus;
}

function updatedOf(ds: Dataset): string | null {
  const raw = ds.updateDateTime ?? ds.createDateTime;
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : formatDatasetDate(d);
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-sm bg-muted/60 px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-semibold tabular-nums">
        {value ?? (
          <>
            <span aria-hidden="true">&ndash;</span>
            <span className="sr-only">Not reported</span>
          </>
        )}
      </dd>
    </div>
  );
}

/**
 * Right-hand rail of the home page: what each dataset is, and what the lookup
 * does and does not disclose. The privacy sentence is the one that used to sit
 * under the query form, moved here unchanged.
 */
export function DatasetRail({ datasets, status }: DatasetRailProps) {
  return (
    <aside aria-label="About this beacon" className="space-y-6">
      {status === 'loading' && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      )}

      {status === 'ready' &&
        datasets.map(ds => (
          <Card key={ds.id}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base leading-snug">{ds.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {ds.description && (
                <p className="text-sm text-muted-foreground">{ds.description}</p>
              )}
              <dl className="grid grid-cols-2 gap-2">
                <Fact
                  label="Variants"
                  value={typeof ds.variantCount === 'number' ? formatNumber(ds.variantCount) : null}
                />
                <Fact
                  label="Samples"
                  value={typeof ds.sampleCount === 'number' ? formatNumber(ds.sampleCount) : null}
                />
                <Fact label="Assembly" value={ds.assemblyId ?? null} />
                <Fact label="Updated" value={updatedOf(ds)} />
              </dl>
            </CardContent>
          </Card>
        ))}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Privacy by design</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This is a privacy-preserving lookup: it reports <strong>whether</strong> a variant is
            present in each dataset — not who carries it. Use the database links on the results to
            jump to allele frequencies and clinical detail.
          </p>
        </CardContent>
      </Card>
    </aside>
  );
}
