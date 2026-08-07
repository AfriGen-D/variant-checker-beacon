import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        // Verdict tones from the shared token set, so a chip cannot be styled
        // with a one-off literal that drifts from its siblings.
        secondary: 'border-transparent bg-quiet-bg text-quiet',
        destructive: 'border-transparent bg-halt text-background',
        // A negative *answer*, not a failure: tinted rather than filled, so
        // YES/NO read as a pair while a real failure stays louder.
        negative: 'border-transparent bg-halt-bg text-halt',
        success: 'border-transparent bg-affirm-bg text-affirm',
        warning: 'border-transparent bg-signal-bg text-signal',
        inert: 'border-transparent bg-inert-bg text-inert',
        info: 'border-transparent bg-primary/15 text-primary',
        outline: 'text-foreground',
      },
      size: {
        sm: 'px-2 py-0.5 text-xs',
        md: 'px-2.5 py-0.5 text-xs',
        lg: 'px-3 py-1 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
);

/**
 * `onClick` is deliberately omitted: a Badge renders a <div>, so an attached
 * handler is unreachable by keyboard and invisible to assistive technology.
 * Put a real <button> inside the badge instead (see DatasetSelector).
 */
export interface BadgeProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onClick'>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant, size }), className)} {...props} />;
}

export { Badge, badgeVariants };
