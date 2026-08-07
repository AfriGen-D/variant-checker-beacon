'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { RecordHead } from './RecordHead';
import { Button } from '@/components/ui/Button';
import type { DatasetAlleleResponse, Dataset, VariantQuery, Handover } from '@/lib/api/types';
import { exportCsv, exportJson } from '@/lib/utils/exportResults';
import { ExternalDbLinks } from '@/components/results/ExternalDbLinks';
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
  const panelId = useId();

  const copy = () => {
    navigator.clipboard.writeText(`curl "${url}"`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`} viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
        API query
      </button>
      {open && (
        <div id={panelId} className="mt-1.5 flex items-center gap-2 bg-muted/70 rounded-md px-3 py-2 border">
          <code className="text-xs font-mono text-muted-foreground break-all flex-1 select-all">
            curl &quot;{url}&quot;
          </code>
          <button
            type="button"
            onClick={copy}
            className="shrink-0 text-xs text-muted-foreground hover:text-foreground transition-colors"
            title={copied ? 'Copied' : 'Copy'}
            aria-label={copied ? 'Copied to clipboard' : 'Copy curl command'}
          >
            <span aria-hidden="true">{copied ? '✓' : '⎘'}</span>
          </button>
        </div>
      )}
    </div>
  );
}

function HandoverButton({ handover, size = 'md' }: { handover: Handover; size?: 'sm' | 'md' }) {
  const sizing = size === 'sm'
    ? 'px-2 py-1 text-xs gap-1'
    : 'px-3 py-1.5 text-sm gap-1.5';
  return (
    <a
      href={handover.url}
      target="_blank"
      rel="noopener noreferrer"
      title={handover.note}
      className={`inline-flex items-center font-medium rounded-md border bg-background hover:bg-muted transition-colors ${sizing}`}
    >
      {handover.handoverType.label}
      <ExternalLink className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
    </a>
  );
}

function ExportButtons({ query, responses }: { query: VariantQuery; responses: DatasetAlleleResponse[] }) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // Set only when the menu is opened from the keyboard, so a mouse user never
  // sees focus jump into the list.
  const focusFirstOnOpen = useRef(false);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  useEffect(() => {
    if (open && focusFirstOnOpen.current) {
      focusFirstOnOpen.current = false;
      itemRefs.current[0]?.focus();
    }
  }, [open]);

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  const onTriggerKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && open) {
      e.preventDefault();
      close(false);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      focusFirstOnOpen.current = true;
      setOpen(true);
    }
  };

  const onItemKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close(true);
    } else if (e.key === 'Tab') {
      setOpen(false);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const count = itemRefs.current.length;
      const next = e.key === 'ArrowDown' ? (index + 1) % count : (index - 1 + count) % count;
      itemRefs.current[next]?.focus();
    }
  };

  const items = [
    { label: 'CSV', rounding: 'rounded-t-md', run: () => exportCsv(query, responses) },
    { label: 'JSON', rounding: 'rounded-b-md', run: () => exportJson(query, responses) },
  ];

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={e => {
          // e.detail === 0 means the click came from Enter/Space, not a pointer.
          focusFirstOnOpen.current = !open && e.detail === 0;
          setOpen(o => !o);
        }}
        onKeyDown={onTriggerKeyDown}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border bg-background hover:bg-muted transition-colors"
      >
        <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        Export
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Export results"
          className="absolute right-0 mt-1 w-32 rounded-md border bg-background shadow-lg z-10"
        >
          {items.map((item, i) => (
            <button
              key={item.label}
              ref={el => {
                itemRefs.current[i] = el;
              }}
              type="button"
              role="menuitem"
              tabIndex={-1}
              className={`block w-full text-left px-4 py-2 text-sm hover:bg-muted focus:bg-muted focus:outline-none transition-colors ${item.rounding}`}
              onKeyDown={e => onItemKeyDown(e, i)}
              onClick={() => { item.run(); close(true); }}
            >
              {item.label}
            </button>
          ))}
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
  const panelId = useId();

  const copy = () => {
    navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`} viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
        JSON response
      </button>
      {open && (
        <div id={panelId} className="mt-1.5 relative bg-muted/70 rounded-md border">
          <button
            type="button"
            onClick={copy}
            className="absolute top-2 right-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
            title={copied ? 'Copied' : 'Copy JSON'}
            aria-label={copied ? 'Copied to clipboard' : 'Copy JSON response'}
          >
            <span aria-hidden="true">{copied ? '✓' : '⎘'}</span>
          </button>
          <pre className="text-xs font-mono text-muted-foreground p-3 overflow-x-auto max-h-80 overflow-y-auto select-all">
            {json}
          </pre>
        </div>
      )}
    </div>
  );
}

export type QueryStatus = 'idle' | 'loading' | 'error' | 'success';

interface DatasetResultsProps {
  datasetAlleleResponses?: DatasetAlleleResponse[];
  datasets?: Dataset[];
  query?: VariantQuery | null;
  selectedDatasetIds?: string[];
  rawResponse?: unknown;
  beaconHandovers?: Handover[];
  status: QueryStatus;
}

export function DatasetResults({ datasetAlleleResponses, datasets, query, selectedDatasetIds, rawResponse, beaconHandovers, status }: DatasetResultsProps) {
  const [page, setPage] = useState(0);

  // Reset to the first page whenever the query, the response, or the dataset
  // selection changes — a shorter list would otherwise render an empty page.
  useEffect(() => {
    setPage(0);
  }, [query, datasetAlleleResponses, selectedDatasetIds]);

  // A query that failed or is still in flight has no verdict to report. The
  // no-results branch below would render "Found in 0 of N" with a red NO per
  // dataset — a definitive negative the beacon never gave.
  if (status === 'error' || status === 'loading') return null;

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
            <RecordHead matched={matched} total={total} hasQuery />
            <div className="flex items-center gap-2">
              {query && <ExportButtons query={query} responses={filteredResponses} />}
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
            {paged.map((dar) => {
              const rowHandovers = dar.resultsHandover?.length ? dar.resultsHandover : beaconHandovers;
              return (
                <div
                  key={dar.datasetId}
                  className="flex items-center justify-between p-3 rounded-lg border bg-muted/50"
                >
                  <p className="font-medium text-sm">{dar.datasetName}</p>
                  <div className="flex items-center gap-2">
                    {dar.exists && dar.alleleFrequency !== undefined && (
                      <span className="text-xs font-mono tabular-nums text-muted-foreground" title="Allele frequency in this dataset">
                        AF {dar.alleleFrequency.toFixed(4)}
                      </span>
                    )}
                    {dar.exists && rowHandovers?.map((h) => (
                      <HandoverButton key={h.handoverType.id + h.url} handover={h} size="sm" />
                    ))}
                    <Badge variant={dar.exists ? 'success' : 'negative'} size="sm">
                      {dar.exists ? 'YES' : 'NO'}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} totalItems={total} />
          {query && (
            <div className="mt-5 pt-4 border-t">
              <ExternalDbLinks query={query} variant="panel" />
            </div>
          )}
          {process.env.NODE_ENV !== 'production' && rawResponse != null && (
            <JsonResponseBlock data={rawResponse} />
          )}
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
        {hasQuery ? (
          <>
            <RecordHead matched={0} total={total} hasQuery />
            <p className="text-sm text-muted-foreground font-mono mt-3">Query: {formatQuery(query)}</p>
            <ApiQueryBlock query={query} />
          </>
        ) : (
          <CardTitle className="text-lg text-muted-foreground">
            {total > 0 ? `${total} dataset${total !== 1 ? 's' : ''} available` : 'Datasets'}
          </CardTitle>
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
                  <Badge variant={hasQuery ? 'negative' : 'secondary'} size="sm">
                    {hasQuery ? 'NO' : (
                      <>
                        <span aria-hidden="true">—</span>
                        <span className="sr-only">Not queried yet</span>
                      </>
                    )}
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
        {hasQuery && query && (
          <div className="mt-5 pt-4 border-t">
            <p className="text-sm text-muted-foreground mb-3">
              Not in these datasets — check whether it appears in the wider databases:
            </p>
            <ExternalDbLinks query={query} variant="panel" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
