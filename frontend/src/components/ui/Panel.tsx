import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * A flat, ruled surface — the Ledger design's primary container.
 *
 * Deliberately not a Card: no large radius, no drop shadow. This app is an
 * instrument, and the elevated-card idiom reads as a content feed. Panels sit
 * flush and are separated by rules, which keeps dense tabular data legible and
 * stops a page of results looking like a stack of unrelated objects.
 *
 * Ported from african-beacon-network so the two surfaces stay recognisably one
 * design system; the beacon adopted that repo's token set in #39 but not this
 * primitive. Card is kept for the places that genuinely want a raised object.
 */
export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-sm border border-border bg-background', className)}
      {...props}
    />
  );
}

interface PanelBarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Right-aligned secondary text — provenance, cache age, counts. */
  meta?: React.ReactNode;
}

/**
 * The strip along the top of a Panel. Monospace and small: it carries machine
 * facts (assembly, record counts, endpoints), not prose, and setting it apart
 * from body text is what keeps it scannable.
 */
export function PanelBar({ className, children, meta, ...props }: PanelBarProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 border-b bg-muted/40 px-4 py-2',
        'font-mono text-[11.5px] text-muted-foreground',
        className,
      )}
      {...props}
    >
      <span className="min-w-0 truncate">{children}</span>
      {meta != null && <span className="shrink-0 tabular-nums">{meta}</span>}
    </div>
  );
}

export function PanelBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...props} />;
}

/**
 * A section eyebrow: wide-tracked uppercase, the smallest type on the page.
 * Labels a region without competing with its heading.
 */
export function Eyebrow({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        'text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
}
