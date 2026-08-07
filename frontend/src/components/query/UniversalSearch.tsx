'use client';

import { useState } from 'react';
import { Search, CornerDownLeft } from 'lucide-react';
import { parseVariantString, type ParsedVariant } from '@/lib/utils/parseVariant';

interface UniversalSearchProps {
  /** Called with parsed fields when the input resolves to a valid variant. */
  onParsed: (parsed: ParsedVariant) => void;
  /**
   * Optionally control the text. Supply both to let a caller write into the box
   * — an example chip, say — so the box always reflects what is being looked
   * up. Omit both and it keeps its own state, which is what a standalone use
   * wants.
   */
  value?: string;
  onValueChange?: (next: string) => void;
}

const FORMAT_HINTS = ['chr11:5225059 G>A', '11-5225059-G-A', '7:117559591', 'X:154360382 G>A'];

/**
 * A single "paste anything" box that accepts the variant notations people copy
 * out of papers, VCFs and other browsers, and fills the structured query form.
 * Parsing happens entirely client-side (see parseVariantString) so there is no
 * round trip just to interpret what the user typed.
 */
export function UniversalSearch({
  onParsed,
  value: controlledValue,
  onValueChange,
}: UniversalSearchProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState('');
  const isControlled = controlledValue !== undefined;
  const value = isControlled ? controlledValue : uncontrolledValue;
  const setValue = (next: string) => {
    if (!isControlled) setUncontrolledValue(next);
    onValueChange?.(next);
  };
  const [error, setError] = useState<string | null>(null);

  const run = () => {
    const result = parseVariantString(value);
    if (!result.ok || !result.parsed) {
      setError(result.error ?? 'Could not understand that variant');
      return;
    }
    setError(null);
    onParsed(result.parsed);
  };

  return (
    <div>
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          inputMode="text"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => { setValue(e.target.value); if (error) setError(null); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); run(); } }}
          placeholder="Paste a variant — e.g. chr11:5225059 G>A or 11-5225059-G-A"
          aria-label="Search for a variant"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? 'universal-search-error' : 'universal-search-hint'}
          className="flex h-14 w-full rounded-xl border border-input bg-background pl-11 pr-28 text-base shadow-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
        <button
          type="button"
          onClick={run}
          className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center gap-1.5 h-10 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          Look up
          <CornerDownLeft className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      {error ? (
        <p id="universal-search-error" className="mt-2 text-sm text-destructive">{error}</p>
      ) : (
        <p id="universal-search-hint" className="mt-2 text-xs text-muted-foreground">
          Accepts{' '}
          {FORMAT_HINTS.map((hint, i) => (
            <span key={hint}>
              {i > 0 && ', '}
              <button
                type="button"
                className="font-mono text-foreground/80 hover:text-primary underline-offset-2 hover:underline"
                onClick={() => { setValue(hint); setError(null); }}
              >
                {hint}
              </button>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
