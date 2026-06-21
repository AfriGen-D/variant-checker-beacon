import type { VariantQueryFormData, RegionQueryFormData } from './validators';
import { CHROMOSOMES, type QueryMode } from './constants';
import type { VariantQuery } from '../api/types';

const validChromosomes = CHROMOSOMES.map((c) => c.value) as string[];

export interface ParsedQuery {
  mode: QueryMode;
  variant?: VariantQueryFormData;
  region?: RegionQueryFormData;
}

/**
 * Parse URL search params into a mode + form data. Backward compatible with the
 * old allele-only URLs (no `mode`): allele params imply Variant, a bare range
 * implies Region. Returns null if the shared coordinates are missing/invalid.
 */
export function queryFromSearchParams(params: URLSearchParams): ParsedQuery | null {
  const assemblyId = params.get('assemblyId');
  const referenceName = params.get('referenceName');
  const startRaw = params.get('start');

  if (!assemblyId || !referenceName || !startRaw) return null;
  if (!validChromosomes.includes(referenceName)) return null;

  const start = Number(startRaw);
  if (!Number.isInteger(start) || start < 0) return null;

  const referenceBases = params.get('referenceBases');
  const alternateBases = params.get('alternateBases');
  const endRaw = params.get('end');
  const end = endRaw ? Number(endRaw) : undefined;
  if (end !== undefined && (!Number.isInteger(end) || end < start)) return null;

  const modeParam = params.get('mode');
  const mode: QueryMode =
    modeParam === 'region'
      ? 'region'
      : modeParam === 'variant'
        ? 'variant'
        : referenceBases && alternateBases
          ? 'variant'
          : end !== undefined
            ? 'region'
            : 'variant';

  if (mode === 'region') {
    if (end === undefined) return null;
    return { mode, region: { assemblyId, referenceName, start, end } };
  }

  if (!referenceBases || !alternateBases) return null;
  return {
    mode,
    variant: {
      assemblyId,
      referenceName,
      start,
      end,
      referenceBases: referenceBases.toUpperCase(),
      alternateBases: alternateBases.toUpperCase(),
    },
  };
}

/**
 * Convert a submitted query into a shareable URL search string, tagged with the
 * mode so the link reopens the right tab.
 */
export function searchParamsFromQuery(query: VariantQuery, mode: QueryMode): string {
  const params = new URLSearchParams();
  params.set('mode', mode);
  params.set('assemblyId', query.assemblyId);
  params.set('referenceName', query.referenceName);
  if (query.start !== undefined) params.set('start', String(query.start));
  if (query.end !== undefined) params.set('end', String(query.end));
  if (query.referenceBases) params.set('referenceBases', query.referenceBases);
  if (query.alternateBases) params.set('alternateBases', query.alternateBases);
  return params.toString();
}
