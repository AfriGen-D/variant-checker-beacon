import type { VariantQuery } from '@/lib/api/types';

/**
 * The query string the UI actually sends to /g_variants, and therefore the one
 * the "API query" block must show.
 *
 * Positions are entered 1-based (the convention of dbSNP, Ensembl and ClinVar)
 * and converted to Beacon v2's 0-based start here: start_0 = start_1 - 1. `end`
 * is unchanged because a 1-based inclusive end equals a 0-based exclusive end.
 * Aggregated granularity is always requested so allele frequencies come back
 * when the beacon has them (it returns a boolean response otherwise).
 *
 * One builder for both the request and the displayed command: a shown command
 * that differs from the sent one returns a different answer when copied.
 */
export function variantQueryParams(query: VariantQuery): URLSearchParams {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    const out = key === 'start' ? Number(value) - 1 : value;
    params.append(key, out.toString());
  });
  if (!params.has('requestedGranularity')) {
    params.append('requestedGranularity', 'aggregated');
  }
  return params;
}
