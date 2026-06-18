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
import { UniversalSearch } from '@/components/query/UniversalSearch';
import { RecentSearches } from '@/components/query/RecentSearches';
import type { ParsedVariant } from '@/lib/utils/parseVariant';
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
    watch,
    formState: { errors },
    reset,
    getValues,
    setFocus,
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

  // Live preview of the variant being assembled, so coordinate/allele mistakes
  // are visible before the query is sent (input is 1-based).
  const w = watch();
  const queryPreview = (() => {
    if (!w.referenceName || w.start === undefined || w.start === null || (w.start as unknown as string) === '') {
      return null;
    }
    const chr = String(w.referenceName).startsWith('chr') ? String(w.referenceName) : `chr${w.referenceName}`;
    const pos = Number(w.start).toLocaleString();
    const range = w.end ? `${pos}–${Number(w.end).toLocaleString()}` : pos;
    const allele = w.referenceBases && w.alternateBases ? ` ${w.referenceBases}>${w.alternateBases}` : '';
    return `${chr}:${range}${allele}`;
  })();

  // Load values into the form and immediately run the query — shared by the
  // example chips, recent-search chips and a fully-specified universal search.
  const applyAndSubmit = (data: VariantQueryFormData) => {
    reset(data);
    handleSubmit(onSubmit)();
  };

  // A pasted/typed variant fills the structured fields. If it's complete we run
  // it; if alleles are missing we just populate and focus the next gap so the
  // user can finish by hand. Current assembly is preserved (rarely in a paste).
  const handleParsed = (parsed: ParsedVariant) => {
    const current = getValues();
    const merged: VariantQueryFormData = {
      assemblyId: current.assemblyId || parsed.data.assemblyId || 'GRCh38',
      referenceName: parsed.data.referenceName ?? '',
      start: parsed.data.start as number,
      end: parsed.data.end,
      referenceBases: parsed.data.referenceBases ?? '',
      alternateBases: parsed.data.alternateBases ?? '',
    };
    if (parsed.complete) {
      applyAndSubmit(merged);
    } else {
      reset(merged);
      if (!merged.referenceBases) setFocus('referenceBases');
      else if (!merged.alternateBases) setFocus('alternateBases');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Check a variant</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Paste a variant in almost any notation, or fill in the fields below.
        </p>
      </CardHeader>
      <CardContent>
        {/* Universal "paste anything" search */}
        <div className="mb-4">
          <UniversalSearch onParsed={handleParsed} />
        </div>

        <div className="mb-6">
          <RecentSearches onSelect={applyAndSubmit} />
        </div>

        {/* Example query chips */}
        <div className="mb-6">
          <p className="text-sm text-muted-foreground mb-2">Or try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border border-primary/20 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/30 transition-colors"
                title={ex.description}
                onClick={() => applyAndSubmit(ex.query as unknown as VariantQueryFormData)}
              >
                {ex.label}
                <span className="text-primary/60 text-xs">({ex.description})</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs uppercase tracking-wide text-muted-foreground">Or enter coordinates</span>
          <div className="h-px flex-1 bg-border" />
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
              placeholder="1-based, e.g. 11796321"
              error={errors.start?.message}
              required
              {...register('start')}
            />
            <Input
              label="End"
              type="number"
              placeholder="Optional, 1-based"
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

          {queryPreview && (
            <div className="rounded-md bg-muted/50 border px-3 py-2 text-sm" aria-live="polite">
              <span className="text-muted-foreground">Querying: </span>
              <span className="font-mono font-medium">{queryPreview}</span>
              <span className="text-muted-foreground text-xs ml-2">(coordinates are 1-based)</span>
            </div>
          )}

          <div className="flex gap-3">
            <Button type="submit" className="flex-1" disabled={isLoading}>
              {isLoading ? 'Checking...' : 'Check variant'}
            </Button>
            <Button type="button" variant="outline" onClick={() => reset()}>
              Reset
            </Button>
          </div>
        </form>

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
