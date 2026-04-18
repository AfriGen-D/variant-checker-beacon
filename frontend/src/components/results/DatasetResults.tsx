'use client';

import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import type { DatasetAlleleResponse, Dataset, VariantQuery } from '@/lib/api/types';
import { exportCsv, exportJson } from '@/lib/utils/exportResults';
import { ExternalLink } from 'lucide-react';

function getApiDisplayBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_BEACON_API_URL;
  if (envUrl) {
    return envUrl.replace(/\/+$/, '').replace(/\/api$/, '') + '/api';
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api`;
  }
  return '/api';
}

function buildAgvdUrl(query: VariantQuery): string {
  const chr = query.referenceName.startsWith('chr') ? query.referenceName : `chr${query.referenceName}`;
  return `https://agvd.afrigen-d.org/search/res?type=coordinate&input=${chr}:${query.start}&dataset=AGVD_24A_Main&page=1`;
}

function buildAgmpUrl(query: VariantQuery): string {
  const chr = query.referenceName.startsWith('chr') ? query.referenceName : `chr${query.referenceName}`;
  return `https://agmp.afrigen-d.org/?search_query=${chr}:${query.start}&model_selection=variantagmp`;
}

const PAGE_SIZE = 5;

function formatQuery(query: VariantQuery): string {
  const chr = query.referenceName.startsWith('chr') ? query.referenceName : `chr${query.referenceName}`;
  const pos = query.start?.toLocaleString() ?? '';
  const alleles = query.referenceBases && query.alternateBases
    ? ` ${query.referenceBases}>${query.alternateBases}`
    : '';
  return `${chr}:${pos}${alleles}`;
}

function buildApiUrl(query: VariantQuery): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.append(key, String(value));
  });
  return `${getApiDisplayBase()}/g_variants?${params.toString()}`;
}

function ApiQueryBlock({ query }: { query: VariantQuery }) {
  const [open, setOpen] = useState(false);
  const url = buildApiUrl(query);
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(`curl "${url}"`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <svg className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`} viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
        API query
      </button>
      {open && (
        <div className="mt-1.5 flex items-center gap-2 bg-muted/70 rounded-md px-3 py-2 border">
          <code className="text-xs font-mono text-muted-foreground break-all flex-1 select-all">
            curl &quot;{url}&quot;
          </code>
          <button onClick={copy} className="shrink-0 text-xs text-muted-foreground hover:text-foreground transition-colors" title="Copy">
            {copied ? '✓' : '⎘'}
          </button>
        </div>
      )}
    </div>
  );
}

function ExportButtons({ query, responses }: { query: VariantQuery; responses: DatasetAlleleResponse[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border bg-background hover:bg-muted transition-colors"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        Export
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-32 rounded-md border bg-background shadow-lg z-10">
          <button
            className="block w-full text-left px-4 py-2 text-sm hover:bg-muted transition-colors rounded-t-md"
            onClick={() => { exportCsv(query, responses); setOpen(false); }}
          >
            CSV
          </button>
          <button
            className="block w-full text-left px-4 py-2 text-sm hover:bg-muted transition-colors rounded-b-md"
            onClick={() => { exportJson(query, responses); setOpen(false); }}
          >
            JSON
          </button>
        </div>
      )}
    </div>
  );
}

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  totalItems: number;
}

function Pagination({ page, totalPages, onPageChange, totalItems }: PaginationProps) {
  if (totalPages <= 1) return null;
  const start = page * PAGE_SIZE + 1;
  const end = Math.min((page + 1) * PAGE_SIZE, totalItems);

  return (
    <div className="flex items-center justify-between pt-4 border-t mt-4">
      <p className="text-xs text-muted-foreground">
        {start}–{end} of {totalItems}
      </p>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function JsonResponseBlock({ data }: { data: unknown }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(data, null, 2);

  const copy = () => {
    navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <svg className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`} viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
        JSON response
      </button>
      {open && (
        <div className="mt-1.5 relative bg-muted/70 rounded-md border">
          <button
            onClick={copy}
            className="absolute top-2 right-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
            title="Copy JSON"
          >
            {copied ? '✓' : '⎘'}
          </button>
          <pre className="text-xs font-mono text-muted-foreground p-3 overflow-x-auto max-h-80 overflow-y-auto select-all">
            {json}
          </pre>
        </div>
      )}
    </div>
  );
}

interface DatasetResultsProps {
  datasetAlleleResponses?: DatasetAlleleResponse[];
  datasets?: Dataset[];
  query?: VariantQuery | null;
  selectedDatasetIds?: string[];
  rawResponse?: unknown;
}

export function DatasetResults({ datasetAlleleResponses, datasets, query, selectedDatasetIds, rawResponse }: DatasetResultsProps) {
  const [page, setPage] = useState(0);

  // Filter by selected datasets (empty = show all)
  const filteredResponses = datasetAlleleResponses && selectedDatasetIds && selectedDatasetIds.length > 0
    ? datasetAlleleResponses.filter(d => selectedDatasetIds.includes(d.datasetId))
    : datasetAlleleResponses;

  const hasResults = filteredResponses && filteredResponses.length > 0;

  if (hasResults) {
    const matched = filteredResponses.filter(d => d.exists).length;
    const total = filteredResponses.length;
    const totalPages = Math.ceil(total / PAGE_SIZE);
    const paged = filteredResponses.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-2xl font-bold">Results</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Found in <span className={matched > 0 ? 'text-emerald-600 font-semibold' : 'text-destructive font-semibold'}>{matched}</span> of {total} dataset{total !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {query && (
                <>
                  <a
                    href={buildAgvdUrl(query)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md border bg-background hover:bg-muted transition-colors"
                  >
                    See in AGVD
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                  <a
                    href={buildAgmpUrl(query)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md border bg-background hover:bg-muted transition-colors"
                  >
                    See in AGMP
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                  <ExportButtons query={query} responses={filteredResponses} />
                </>
              )}
            </div>
          </div>
          {query && (
            <>
              <p className="text-sm text-muted-foreground font-mono mt-1">Query: {formatQuery(query)}</p>
              <ApiQueryBlock query={query} />
            </>
          )}
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {paged.map((dar) => (
              <div
                key={dar.datasetId}
                className="flex items-center justify-between p-3 rounded-lg border bg-muted/50"
              >
                <p className="font-medium text-sm">{dar.datasetName}</p>
                <Badge variant={dar.exists ? 'success' : 'destructive'} size="sm">
                  {dar.exists ? 'YES' : 'NO'}
                </Badge>
              </div>
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} totalItems={total} />
          {rawResponse != null && <JsonResponseBlock data={rawResponse} />}
        </CardContent>
      </Card>
    );
  }

  const hasQuery = !!query;
  const allDatasets = datasets ?? [];
  const total = allDatasets.length;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const paged = allDatasets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <Card>
      <CardHeader>
        <CardTitle className={hasQuery ? 'text-2xl font-bold' : 'text-lg text-muted-foreground'}>
          {hasQuery ? 'Results' : (total > 0 ? `${total} dataset${total !== 1 ? 's' : ''} available` : 'Datasets')}
        </CardTitle>
        {hasQuery && (
          <>
            <p className="text-sm text-muted-foreground mt-1">
              Found in <span className="text-destructive font-semibold">0</span> of {total} dataset{total !== 1 ? 's' : ''}
            </p>
            <p className="text-sm text-muted-foreground font-mono mt-1">Query: {formatQuery(query)}</p>
            <ApiQueryBlock query={query} />
          </>
        )}
      </CardHeader>
      <CardContent>
        {total > 0 ? (
          <>
            <div className="space-y-3">
              {paged.map((ds) => (
                <div
                  key={ds.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-muted/50"
                >
                  <p className="font-medium text-sm">{ds.name}</p>
                  <Badge variant={hasQuery ? 'destructive' : 'secondary'} size="sm">
                    {hasQuery ? 'NO' : '—'}
                  </Badge>
                </div>
              ))}
            </div>
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} totalItems={total} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            Submit a query to see results
          </p>
        )}
      </CardContent>
    </Card>
  );
}
