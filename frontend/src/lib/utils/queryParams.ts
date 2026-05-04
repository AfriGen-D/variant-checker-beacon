import type { VariantQueryFormData } from './validators';
import { CHROMOSOMES } from './constants';

const validChromosomes = CHROMOSOMES.map(c => c.value) as string[];

/**
 * Parse URL search params into form data.
 * Returns null if required fields are missing or invalid.
 */
export function queryFromSearchParams(
  params: URLSearchParams
): VariantQueryFormData | null {
  const assemblyId = params.get('assemblyId');
  const referenceName = params.get('referenceName');
  const startRaw = params.get('start');
  const referenceBases = params.get('referenceBases');
  const alternateBases = params.get('alternateBases');

  if (!assemblyId || !referenceName || !startRaw || !referenceBases || !alternateBases) {
    return null;
  }

  const start = Number(startRaw);
  if (!Number.isInteger(start) || start < 0) return null;
  if (!validChromosomes.includes(referenceName)) return null;

  const endRaw = params.get('end');
  const end = endRaw ? Number(endRaw) : undefined;
  if (end !== undefined && (!Number.isInteger(end) || end < start)) return null;

  return {
    assemblyId,
    referenceName,
    start,
    end,
    referenceBases: referenceBases.toUpperCase(),
    alternateBases: alternateBases.toUpperCase(),
  };
}

/**
 * Convert form data into URL search params string.
 */
export function searchParamsFromQuery(query: VariantQueryFormData): string {
  const params = new URLSearchParams();
  params.set('assemblyId', query.assemblyId);
  params.set('referenceName', query.referenceName);
  params.set('start', String(query.start));
  if (query.end !== undefined) params.set('end', String(query.end));
  params.set('referenceBases', query.referenceBases);
  params.set('alternateBases', query.alternateBases);
  return params.toString();
}
