import type { DatasetAlleleResponse, VariantQuery } from '../api/types';

export function buildExportFilename(query: VariantQuery, extension: string): string {
  const chr = query.referenceName;
  const pos = query.start ?? '';
  const ref = query.referenceBases ?? '';
  const alt = query.alternateBases ?? '';
  return `beacon-query-chr${chr}-${pos}-${ref}-${alt}.${extension}`;
}

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportCsv(
  query: VariantQuery,
  responses: DatasetAlleleResponse[]
) {
  const header = 'assembly,chromosome,start,ref,alt,dataset_name,dataset_id,exists,allele_frequency';
  const rows = responses.map(r =>
    [
      query.assemblyId,
      query.referenceName,
      query.start ?? '',
      query.referenceBases ?? '',
      query.alternateBases ?? '',
      `"${(r.datasetName ?? '').replace(/"/g, '""')}"`,
      r.datasetId,
      r.exists,
      r.alleleFrequency ?? '',
    ].join(',')
  );
  const csv = [header, ...rows].join('\n');
  downloadBlob(csv, buildExportFilename(query, 'csv'), 'text/csv;charset=utf-8;');
}

export function exportJson(
  query: VariantQuery,
  responses: DatasetAlleleResponse[]
) {
  const matched = responses.filter(r => r.exists).length;
  const payload = {
    query: {
      assemblyId: query.assemblyId,
      referenceName: query.referenceName,
      start: query.start,
      end: query.end,
      referenceBases: query.referenceBases,
      alternateBases: query.alternateBases,
    },
    summary: {
      totalDatasets: responses.length,
      matchedDatasets: matched,
    },
    datasetAlleleResponses: responses,
  };
  const json = JSON.stringify(payload, null, 2);
  downloadBlob(json, buildExportFilename(query, 'json'), 'application/json;charset=utf-8;');
}
