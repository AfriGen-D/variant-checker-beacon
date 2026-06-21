'use client';

import { Button } from '@/components/ui/Button';
import { DatasetSelector } from '@/components/query/DatasetSelector';
import { FilterSelector } from '@/components/query/FilterSelector';
import type { Dataset } from '@/lib/api/types';

interface QueryActionsProps {
  /** Formatted "what will be queried" string, or null to hide the preview. */
  preview: string | null;
  isLoading?: boolean;
  submitLabel: string;
  loadingLabel: string;
  onReset: () => void;
  datasets?: Dataset[];
  selectedDatasetIds?: string[];
  onSelectedDatasetsChange?: (ids: string[]) => void;
  filters?: string[];
  onFiltersChange?: (filters: string[]) => void;
}

/**
 * The shared tail of every query mode: dataset picker, optional filtering
 * terms, a live preview of the assembled query, and the submit/reset row. Lives
 * inside the enclosing <form> so the submit button drives react-hook-form.
 */
export function QueryActions({
  preview,
  isLoading = false,
  submitLabel,
  loadingLabel,
  onReset,
  datasets,
  selectedDatasetIds,
  onSelectedDatasetsChange,
  filters,
  onFiltersChange,
}: QueryActionsProps) {
  return (
    <div className="space-y-4">
      {datasets && datasets.length > 1 && onSelectedDatasetsChange && (
        <DatasetSelector
          datasets={datasets}
          selectedDatasetIds={selectedDatasetIds ?? []}
          onChange={onSelectedDatasetsChange}
        />
      )}

      {onFiltersChange && (
        <FilterSelector selected={filters ?? []} onChange={onFiltersChange} />
      )}

      {preview && (
        <div className="rounded-md bg-muted/50 border px-3 py-2 text-sm" aria-live="polite">
          <span className="text-muted-foreground">Querying: </span>
          <span className="font-mono font-medium">{preview}</span>
          <span className="text-muted-foreground text-xs ml-2">(coordinates are 1-based)</span>
        </div>
      )}

      <div className="flex gap-3">
        <Button type="submit" className="flex-1" disabled={isLoading}>
          {isLoading ? loadingLabel : submitLabel}
        </Button>
        <Button type="button" variant="outline" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}
