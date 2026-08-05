'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { regionQuerySchema, type RegionQueryFormData } from '@/lib/utils/validators';
import { ASSEMBLIES, CHROMOSOMES, REGION_EXAMPLES, FIELD_HINTS } from '@/lib/utils/constants';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { QueryActions } from '@/components/query/QueryActions';
import type { Dataset, VariantQuery } from '@/lib/api/types';

interface RegionQueryFormProps {
  onSubmit: (query: VariantQuery) => void;
  isLoading?: boolean;
  filters?: string[];
  onFiltersChange?: (filters: string[]) => void;
  initialValues?: RegionQueryFormData | null;
  datasets?: Dataset[];
  selectedDatasetIds?: string[];
  onSelectedDatasetsChange?: (ids: string[]) => void;
}

/**
 * Region (range) query: every variant overlapping [start, end] on a
 * chromosome. No allele fields — the backend builds an overlap query and the
 * range is capped at 10M bases (enforced by regionQuerySchema).
 */
export function RegionQueryForm({
  onSubmit,
  isLoading = false,
  filters,
  onFiltersChange,
  initialValues,
  datasets,
  selectedDatasetIds,
  onSelectedDatasetsChange,
}: RegionQueryFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
    reset,
  } = useForm<RegionQueryFormData>({
    resolver: zodResolver(regionQuerySchema),
    defaultValues: initialValues ?? {
      assemblyId: 'GRCh38',
      referenceName: '',
      start: undefined as unknown as number,
      end: undefined as unknown as number,
    },
  });

  const w = watch();
  const preview = (() => {
    if (!w.referenceName || !w.start || !w.end) return null;
    const chr = String(w.referenceName).startsWith('chr') ? String(w.referenceName) : `chr${w.referenceName}`;
    return `${chr}:${Number(w.start).toLocaleString()}–${Number(w.end).toLocaleString()}`;
  })();

  const submit = (data: RegionQueryFormData) => {
    onSubmit({
      assemblyId: data.assemblyId,
      referenceName: data.referenceName,
      start: data.start,
      end: data.end,
    });
  };

  const applyExample = (q: RegionQueryFormData) => {
    reset(q);
    handleSubmit(submit)();
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Find every variant overlapping a coordinate range on one chromosome.
      </p>

      <div>
        <p className="text-sm text-muted-foreground mb-2">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {REGION_EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border border-primary/20 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/30 transition-colors"
              title={ex.description}
              onClick={() => applyExample(ex.query as unknown as RegionQueryFormData)}
            >
              {ex.label}
              <span className="text-primary/60 text-xs">({ex.description})</span>
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit(submit)} className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Select
            label="Assembly"
            tooltip={FIELD_HINTS.assembly}
            options={ASSEMBLIES}
            error={errors.assemblyId?.message}
            required
            {...register('assemblyId')}
          />
          <Select
            label="Chromosome"
            tooltip={FIELD_HINTS.chromosome}
            options={CHROMOSOMES}
            placeholder="Select"
            error={errors.referenceName?.message}
            required
            {...register('referenceName')}
          />
          <Input
            label="Start"
            tooltip={FIELD_HINTS.regionStart}
            type="number"
            placeholder="1-based, e.g. 5225000"
            error={errors.start?.message}
            required
            {...register('start')}
          />
          <Input
            label="End"
            tooltip={FIELD_HINTS.regionEnd}
            type="number"
            placeholder="1-based, e.g. 5229000"
            error={errors.end?.message}
            required
            {...register('end')}
          />
        </div>

        <QueryActions
          preview={preview}
          isLoading={isLoading}
          submitLabel="Search region"
          loadingLabel="Searching…"
          onReset={() => reset()}
          datasets={datasets}
          selectedDatasetIds={selectedDatasetIds}
          onSelectedDatasetsChange={onSelectedDatasetsChange}
          filters={filters}
          onFiltersChange={onFiltersChange}
        />
      </form>
    </div>
  );
}
