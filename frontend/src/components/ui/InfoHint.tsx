'use client';

import * as React from 'react';
import { Info } from 'lucide-react';
import { cn } from '@/lib/utils';

interface InfoHintProps {
  /** Plain-language help text shown on hover/focus. */
  text: string;
  /** Accessible name for the trigger; defaults to "More information". */
  label?: string;
  className?: string;
}

/**
 * A small "ⓘ" affordance that reveals a short help bubble on hover or keyboard
 * focus. CSS-only (group-hover + group-focus-within) so it works for both mouse
 * and keyboard users without a tooltip library, and the bubble is tied to the
 * trigger via aria-describedby for screen readers.
 */
export function InfoHint({ text, label = 'More information', className }: InfoHintProps) {
  const id = React.useId();
  return (
    <span className={cn('group relative inline-flex align-middle', className)}>
      <button
        type="button"
        aria-label={label}
        aria-describedby={id}
        className="inline-flex items-center justify-center text-muted-foreground/70 hover:text-foreground focus-visible:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-full"
      >
        <Info className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-20 mt-1.5 w-56 -translate-x-1/2 rounded-md border bg-popover px-2.5 py-1.5 text-xs font-normal leading-snug text-popover-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
