'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { variantQuerySchema, type VariantQueryFormData } from '@/lib/utils/validators';
import { ASSEMBLIES, CHROMOSOMES, EXAMPLE_QUERIES } from '@/lib/utils/constants';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Separator } from '@/components/ui/Separator';
import { FilterSelector } from '@/components/query/FilterSelector';
import type { Dataset } from '@/lib/api/types';

interface VariantQueryFormProps {
  onSubmit: (data: VariantQueryFormData) => void;
  isLoading?: boolean;
  filters?: string[];
  onFiltersChange?: (filters: string[]) => void;
  initialValues?: VariantQueryFormData | null;
  datasets?: Dataset[];
  selectedDatasetIds?: string[];
  onSelectedDatasetsChange?: (ids: string[]) => void;
}

export function VariantQueryForm({ onSubmit, isLoading = false, filters, onFiltersChange, initialValues, datasets, selectedDatasetIds, onSelectedDatasetsChange }: VariantQueryFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<VariantQueryFormData>({
    resolver: zodResolver(variantQuerySchema),
    defaultValues: initialValues ?? {
      assemblyId: 'GRCh38',
      referenceName: '',
      start: undefined,
      end: undefined,
      referenceBases: '',
      alternateBases: '',
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Query Genomic Variants</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Example query chips */}
        <div className="mb-6">
          <p className="text-sm text-muted-foreground mb-2">Try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border border-primary/20 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/30 transition-colors"
                title={ex.description}
                onClick={() => {
                  reset(ex.query);
                  handleSubmit(onSubmit)();
                }}
              >
                {ex.label}
                <span className="text-primary/60 text-xs">({ex.description})</span>
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Select
              label="Assembly"
              options={ASSEMBLIES}
              error={errors.assemblyId?.message}
              required
              {...register('assemblyId')}
            />
            <Select
              label="Chromosome"
              options={CHROMOSOMES}
              placeholder="Select"
              error={errors.referenceName?.message}
              required
              {...register('referenceName')}
            />
            <Input
              label="Start"
              type="number"
              placeholder="e.g., 100000"
              error={errors.start?.message}
              required
              {...register('start')}
            />
            <Input
              label="End"
              type="number"
              placeholder="Optional"
              error={errors.end?.message}
              {...register('end')}
            />
            <Input
              label="Ref"
              type="text"
              placeholder="e.g., A"
              error={errors.referenceBases?.message}
              required
              {...register('referenceBases')}
            />
            <Input
              label="Alt"
              type="text"
              placeholder="e.g., T"
              error={errors.alternateBases?.message}
              required
              {...register('alternateBases')}
            />
          </div>

          {datasets && datasets.length > 1 && onSelectedDatasetsChange && (
            <div>
              <p className="text-sm font-medium mb-2">Datasets to query</p>
              <div className="flex flex-wrap gap-3">
                {datasets.map(ds => {
                  const checked = !selectedDatasetIds || selectedDatasetIds.length === 0 || selectedDatasetIds.includes(ds.id);
                  return (
                    <label key={ds.id} className="inline-flex items-center gap-1.5 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          const allIds = datasets.map(d => d.id);
                          // If nothing selected, treat as all selected
                          const current = (!selectedDatasetIds || selectedDatasetIds.length === 0)
                            ? [...allIds]
                            : [...selectedDatasetIds];
                          const next = checked
                            ? current.filter(id => id !== ds.id)
                            : [...current, ds.id];
                          // If all selected again, clear to empty (= all)
                          onSelectedDatasetsChange(next.length === allIds.length ? [] : next);
                        }}
                        className="rounded border-border"
                      />
                      {ds.name}
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {onFiltersChange && (
            <FilterSelector selected={filters ?? []} onChange={onFiltersChange} />
          )}

          <div className="flex gap-3">
            <Button type="submit" className="flex-1" disabled={isLoading}>
              {isLoading ? 'Querying...' : 'Query Beacon'}
            </Button>
            <Button type="button" variant="outline" onClick={() => reset()}>
              Reset
            </Button>
          </div>
        </form>

        <Separator className="mt-6" />
        <p className="text-sm text-muted-foreground mt-4">
          <strong>Boolean Mode:</strong> This query will return YES or NO indicating whether the
          variant exists in the database.
        </p>
      </CardContent>
    </Card>
  );
}
