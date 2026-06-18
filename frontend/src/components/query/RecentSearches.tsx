'use client';

import { History, X } from 'lucide-react';
import { useQueryStore } from '@/lib/store/queryStore';
import type { VariantQuery } from '@/lib/api/types';
import type { VariantQueryFormData } from '@/lib/utils/validators';

interface RecentSearchesProps {
  /** Re-run a past search by loading it back into the form. */
  onSelect: (data: VariantQueryFormData) => void;
  max?: number;
}

function label(query: VariantQuery): string {
  const chr = query.referenceName.startsWith('chr') ? query.referenceName : `chr${query.referenceName}`;
  const alleles = query.referenceBases && query.alternateBases
    ? ` ${query.referenceBases}>${query.alternateBases}`
    : '';
  return `${chr}:${query.start?.toLocaleString() ?? ''}${alleles}`;
}

function toFormData(query: VariantQuery): VariantQueryFormData {
  return {
    assemblyId: query.assemblyId,
    referenceName: query.referenceName,
    start: query.start as number,
    end: query.end,
    referenceBases: query.referenceBases ?? '',
    alternateBases: query.alternateBases ?? '',
  };
}

/**
 * Surfaces the query history that already lives in the Zustand store but was
 * never shown in the UI — turning one-off lookups into a browsable trail and
 * giving the tool a "session memory" that a general checker is expected to have.
 */
export function RecentSearches({ onSelect, max = 6 }: RecentSearchesProps) {
  const { queryHistory, clearHistory } = useQueryStore();
  if (queryHistory.length === 0) return null;

  const items = queryHistory.slice(0, max);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <History className="h-3.5 w-3.5" aria-hidden="true" />
          Recent lookups
        </p>
        <button
          type="button"
          onClick={clearHistory}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Clear
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item, i) => {
          const found = item.result?.response?.exists;
          return (
            <button
              key={`${label(item.query)}-${i}`}
              type="button"
              onClick={() => onSelect(toFormData(item.query))}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-full border bg-background hover:bg-muted hover:border-primary/30 transition-colors"
              title={`Re-run ${label(item.query)}`}
            >
              <span
                className={
                  found === undefined
                    ? 'h-1.5 w-1.5 rounded-full bg-muted-foreground/40'
                    : found
                      ? 'h-1.5 w-1.5 rounded-full bg-emerald-500'
                      : 'h-1.5 w-1.5 rounded-full bg-destructive'
                }
                aria-hidden="true"
              />
              <span className="font-mono">{label(item.query)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
