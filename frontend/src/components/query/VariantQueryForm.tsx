'use client';

import { useId, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { variantQuerySchema, type VariantQueryFormData } from '@/lib/utils/validators';
import { ASSEMBLIES, CHROMOSOMES, EXAMPLE_QUERIES, FIELD_HINTS } from '@/lib/utils/constants';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { QueryActions } from '@/components/query/QueryActions';
import { UniversalSearch } from '@/components/query/UniversalSearch';
import { RecentSearches } from '@/components/query/RecentSearches';
import type { ParsedVariant } from '@/lib/utils/parseVariant';
import type { Dataset, VariantQuery } from '@/lib/api/types';

interface VariantQueryFormProps {
  onSubmit: (query: VariantQuery) => void;
  isLoading?: boolean;
  filters?: string[];
  onFiltersChange?: (filters: string[]) => void;
  initialValues?: VariantQueryFormData | null;
  datasets?: Dataset[];
  selectedDatasetIds?: string[];
  onSelectedDatasetsChange?: (ids: string[]) => void;
}

/**
 * Variant (exact) query: a specific ref → alt change at one position. Keeps the
 * rich entry affordances — paste box, recent lookups, example chips — since a
 * pasted/typed variant always resolves to this mode.
 */
export function VariantQueryForm({
  onSubmit,
  isLoading = false,
  filters,
  onFiltersChange,
  initialValues,
  datasets,
  selectedDatasetIds,
  onSelectedDatasetsChange,
}: VariantQueryFormProps) {
  const [examplesOpen, setExamplesOpen] = useState(false);
  const examplesId = useId();
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

  const submit = (data: VariantQueryFormData) => {
    onSubmit({
      assemblyId: data.assemblyId,
      referenceName: data.referenceName,
      start: data.start,
      end: data.end,
      referenceBases: data.referenceBases,
      alternateBases: data.alternateBases,
    });
  };

  // Load values into the form and immediately run the query — shared by the
  // example chips, recent-search chips and a fully-specified universal search.
  const applyAndSubmit = (data: VariantQueryFormData) => {
    reset(data);
    handleSubmit(submit)();
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
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Check whether a specific change at one position is present in each dataset.
      </p>

      {/* Universal "paste anything" search */}
      <UniversalSearch onParsed={handleParsed} />

      <RecentSearches onSelect={applyAndSubmit} />

      {/* Example query chips — collapsed by default. Six chips with parenthetical
          descriptions crowd out the search box, which is the primary action. */}
      <div>
        <button
          type="button"
          onClick={() => setExamplesOpen(o => !o)}
          aria-expanded={examplesOpen}
          aria-controls={examplesId}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          <svg
            aria-hidden="true"
            className={`h-3 w-3 transition-transform ${examplesOpen ? 'rotate-90' : ''}`}
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
          </svg>
          Or try an example
        </button>
        {examplesOpen && (
          <div id={examplesId} className="flex flex-wrap gap-2 mt-2">
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
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-wide text-muted-foreground">Or enter coordinates</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSubmit(submit)} className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
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
            tooltip={FIELD_HINTS.start}
            type="number"
            placeholder="1-based, e.g. 11796321"
            error={errors.start?.message}
            required
            {...register('start')}
          />
          <Input
            label="End"
            tooltip={FIELD_HINTS.end}
            type="number"
            placeholder="Optional, 1-based"
            error={errors.end?.message}
            {...register('end')}
          />
          <Input
            label="Ref"
            tooltip={FIELD_HINTS.ref}
            type="text"
            placeholder="e.g., A"
            error={errors.referenceBases?.message}
            required
            {...register('referenceBases')}
          />
          <Input
            label="Alt"
            tooltip={FIELD_HINTS.alt}
            type="text"
            placeholder="e.g., T"
            error={errors.alternateBases?.message}
            required
            {...register('alternateBases')}
          />
        </div>

        <QueryActions
          preview={queryPreview}
          isLoading={isLoading}
          submitLabel="Check variant"
          loadingLabel="Checking…"
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
