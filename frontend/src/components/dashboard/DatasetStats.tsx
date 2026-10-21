'use client';

import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDatasetDate, summariseDatasets } from '@/lib/utils/datasetStats';
import { formatNumber } from '@/lib/utils/formatters';
import type { Dataset } from '@/lib/api/types';

export type DatasetsStatus = 'loading' | 'ready' | 'error';

interface DatasetStatsProps {
  datasets: Dataset[];
  status: DatasetsStatus;
}

interface Tile {
  label: string;
  /** null means the beacon did not report it: shown as a dash, never as 0. */
  value: string | null;
  note: string;
}

/**
 * At-a-glance facts about what this beacon holds, taken from the same
 * /datasets response the rest of the page already loads. A failed load renders
 * nothing: "0 datasets" would be a claim the beacon never made.
 */
export function DatasetStats({ datasets, status }: DatasetStatsProps) {
  if (status === 'error') return null;

  const tiles: Tile[] | null =
    status === 'ready'
      ? (() => {
          const s = summariseDatasets(datasets);
          return [
            {
              label: 'Datasets',
              value: formatNumber(s.datasetCount),
              note: 'available to query',
            },
            {
              label: 'Variants',
              value: s.variantCount === null ? null : formatNumber(s.variantCount),
              note: 'across all datasets',
            },
            {
              label: 'Samples',
              value: s.sampleCount === null ? null : formatNumber(s.sampleCount),
              note: 'in the reference panels',
            },
            {
              label: 'Assembly',
              value: s.assemblies.length === 0 ? null : s.assemblies.join(', '),
              note: 'genome build',
            },
            {
              label: 'Updated',
              value: s.updated === null ? null : formatDatasetDate(s.updated),
              note: 'latest dataset release',
            },
          ];
        })()
      : null;

  const labels = ['Datasets', 'Variants', 'Samples', 'Assembly', 'Updated'];

  return (
    <section
      aria-label="Dataset summary"
      aria-busy={status === 'loading' || undefined}
      className="mb-6 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(10.5rem,1fr))]"
    >
      {(tiles ?? labels.map(label => ({ label, value: null, note: '' }))).map(tile => (
        <Card key={tile.label} className="p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {tile.label}
          </p>
          {tiles === null ? (
            <Skeleton className="mt-2 h-8 w-24" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums leading-tight">
              {tile.value ?? (
                <>
                  <span aria-hidden="true">&ndash;</span>
                  <span className="sr-only">Not reported</span>
                </>
              )}
            </p>
          )}
          {tiles !== null && <p className="mt-1 text-xs text-muted-foreground">{tile.note}</p>}
        </Card>
      ))}
    </section>
  );
}
