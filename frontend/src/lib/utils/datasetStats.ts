import type { Dataset } from '@/lib/api/types';

export interface DatasetSummary {
  datasetCount: number;
  /** Sum across datasets, or null when any dataset does not report a count. */
  variantCount: number | null;
  /** Sum across datasets, or null when any dataset does not report a count. */
  sampleCount: number | null;
  /** Distinct assembly ids, in first-seen order. */
  assemblies: string[];
  /** Most recent update (or creation) time across datasets, or null if none is parseable. */
  updated: Date | null;
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

/**
 * A sum is only reported when every dataset contributes to it. A partial sum
 * would read as the beacon's total while silently leaving a dataset out, so an
 * unknown count makes the whole figure unknown rather than smaller.
 */
function sumOrNull(values: Array<number | undefined>): number | null {
  if (values.length === 0 || !values.every(isCount)) return null;
  return values.reduce<number>((total, v) => total + (v as number), 0);
}

function latest(dates: Array<string | undefined>): Date | null {
  let best: Date | null = null;
  for (const raw of dates) {
    if (!raw) continue;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) continue;
    if (best === null || d > best) best = d;
  }
  return best;
}

export function summariseDatasets(datasets: Dataset[]): DatasetSummary {
  const assemblies: string[] = [];
  for (const ds of datasets) {
    if (ds.assemblyId && !assemblies.includes(ds.assemblyId)) assemblies.push(ds.assemblyId);
  }
  return {
    datasetCount: datasets.length,
    variantCount: sumOrNull(datasets.map(ds => ds.variantCount)),
    sampleCount: sumOrNull(datasets.map(ds => ds.sampleCount)),
    assemblies,
    updated: latest(datasets.map(ds => ds.updateDateTime ?? ds.createDateTime)),
  };
}

/** "6 May 2026". Pinned to UTC so the day does not shift with the viewer's zone. */
export function formatDatasetDate(date: Date): string {
  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
