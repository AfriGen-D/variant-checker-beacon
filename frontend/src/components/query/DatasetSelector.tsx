'use client';

import { useMemo } from 'react';
import { X } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Select';
import { InfoHint } from '@/components/ui/InfoHint';
import { FIELD_HINTS } from '@/lib/utils/constants';
import type { Dataset } from '@/lib/api/types';

interface DatasetSelectorProps {
  datasets: Dataset[];
  /** Empty array means "all datasets" (the backend default). */
  selectedDatasetIds: string[];
  onChange: (ids: string[]) => void;
}

/**
 * Chip-based dataset picker. Selected panels show as removable chips; an "add"
 * menu offers the rest. An empty selection is treated as "all" (matching the
 * backend default), so the stored value is cleared whenever every dataset is
 * selected.
 */
export function DatasetSelector({ datasets, selectedDatasetIds, onChange }: DatasetSelectorProps) {
  const allIds = useMemo(() => datasets.map((d) => d.id), [datasets]);

  // Effective selection: an empty stored value means every dataset.
  const effective = selectedDatasetIds.length === 0 ? allIds : selectedDatasetIds;
  const unselected = datasets.filter((d) => !effective.includes(d.id));

  // Normalize back to "all" (empty) whenever the result covers every dataset.
  const commit = (next: string[]) => onChange(next.length === allIds.length ? [] : next);

  const remove = (id: string) => commit(effective.filter((x) => x !== id));
  const add = (id: string) => {
    if (!id || effective.includes(id)) return;
    commit([...effective, id]);
  };

  const nameOf = (id: string) => datasets.find((d) => d.id === id)?.name ?? id;

  return (
    <div>
      <p className="text-sm font-medium mb-2">
        Datasets to query
        <InfoHint text={FIELD_HINTS.datasets} label="About datasets" className="ml-1" />
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {effective.map((id) => (
          <Badge key={id} variant="info" size="md" className="gap-1.5">
            {nameOf(id)}
            {effective.length > 1 && (
              <button
                type="button"
                aria-label={`Remove ${nameOf(id)}`}
                onClick={() => remove(id)}
                className="-mr-0.5 rounded-full hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </Badge>
        ))}

        {unselected.length > 0 && (
          <div className="w-48">
            <Select
              aria-label="Add a dataset"
              value=""
              onChange={(e) => add(e.target.value)}
              placeholder="Add dataset…"
              options={unselected.map((d) => ({ value: d.id, label: d.name }))}
            />
          </div>
        )}
      </div>
    </div>
  );
}
