'use client';

import { useRef } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Separator } from '@/components/ui/Separator';
import { Badge } from '@/components/ui/Badge';
import { VariantQueryForm } from '@/components/query/VariantQueryForm';
import { RegionQueryForm } from '@/components/query/RegionQueryForm';
import { QUERY_MODES, type QueryMode } from '@/lib/utils/constants';
import { cn } from '@/lib/utils';
import type { Dataset, VariantQuery } from '@/lib/api/types';
import type { VariantQueryFormData, RegionQueryFormData } from '@/lib/utils/validators';

interface QueryConsoleProps {
  mode: QueryMode;
  onModeChange: (mode: QueryMode) => void;
  onSubmit: (query: VariantQuery, mode: QueryMode) => void;
  isLoading?: boolean;
  filters?: string[];
  onFiltersChange?: (filters: string[]) => void;
  datasets?: Dataset[];
  selectedDatasetIds?: string[];
  onSelectedDatasetsChange?: (ids: string[]) => void;
  initialVariant?: VariantQueryFormData | null;
  initialRegion?: RegionQueryFormData | null;
}

/**
 * The search console: a tabbed shell over the query modes (Variant / Region /
 * Gene). One backend, several entry grammars — the user picks how to express
 * the query rather than being forced into one coordinate form.
 */
export function QueryConsole({
  mode,
  onModeChange,
  onSubmit,
  isLoading,
  filters,
  onFiltersChange,
  datasets,
  selectedDatasetIds,
  onSelectedDatasetsChange,
  initialVariant,
  initialRegion,
}: QueryConsoleProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const available = QUERY_MODES.filter((m) => m.available);

  // Roving arrow-key navigation across the enabled tabs.
  const onTabKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const order = QUERY_MODES.map((m) => m.value);
    const enabled = available.map((m) => m.value);
    const pos = enabled.indexOf(QUERY_MODES[index].value);
    const nextValue =
      e.key === 'ArrowRight'
        ? enabled[(pos + 1) % enabled.length]
        : enabled[(pos - 1 + enabled.length) % enabled.length];
    onModeChange(nextValue);
    const nextIndex = order.indexOf(nextValue);
    tabRefs.current[nextIndex]?.focus();
  };

  const shared = {
    isLoading,
    filters,
    onFiltersChange,
    datasets,
    selectedDatasetIds,
    onSelectedDatasetsChange,
  };

  return (
    <Card>
      <CardContent className="pt-6">
        {/* Mode tabs */}
        <div role="tablist" aria-label="Query mode" className="flex flex-wrap gap-1 border-b mb-5">
          {QUERY_MODES.map((m, i) => {
            const selected = m.value === mode;
            return (
              <button
                key={m.value}
                ref={(el) => {
                  tabRefs.current[i] = el;
                }}
                role="tab"
                id={`query-tab-${m.value}`}
                aria-selected={selected}
                aria-controls="query-tabpanel"
                aria-disabled={!m.available || undefined}
                tabIndex={selected ? 0 : -1}
                title={m.description}
                onClick={() => m.available && onModeChange(m.value)}
                onKeyDown={(e) => m.available && onTabKeyDown(e, i)}
                className={cn(
                  '-mb-px inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                  selected
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
                  !m.available && 'cursor-not-allowed opacity-60 hover:text-muted-foreground hover:border-transparent'
                )}
              >
                {m.label}
                {!m.available && (
                  <Badge variant="secondary" size="sm" className="font-normal">
                    soon
                  </Badge>
                )}
              </button>
            );
          })}
        </div>

        <div id="query-tabpanel" role="tabpanel" aria-labelledby={`query-tab-${mode}`}>
          {mode === 'variant' && (
            <VariantQueryForm
              {...shared}
              initialValues={initialVariant}
              onSubmit={(q) => onSubmit(q, 'variant')}
            />
          )}
          {mode === 'region' && (
            <RegionQueryForm
              {...shared}
              initialValues={initialRegion}
              onSubmit={(q) => onSubmit(q, 'region')}
            />
          )}
          {mode === 'gene' && (
            <p className="text-sm text-muted-foreground py-6">
              Gene search is coming soon — use the Variant or Region tab for now.
            </p>
          )}
        </div>

        <Separator className="mt-6" />
        <p className="text-sm text-muted-foreground mt-4">
          This is a privacy-preserving lookup: it reports <strong>whether</strong> a variant is
          present in each dataset — not who carries it. Use the database links on the results to
          jump to allele frequencies and clinical detail.
        </p>
      </CardContent>
    </Card>
  );
}
