import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary/20 text-secondary',
        destructive: 'border-transparent bg-destructive text-destructive-foreground',
        // A negative *answer*, not a failure. In a discovery beacon "not
        // present" is the most common and entirely correct result, so it keeps
        // the red family — YES/NO still read as a pair — but tinted rather
        // than filled. `destructive` stays reserved for the beacon failing to
        // answer at all, which must stay visually louder.
        negative: 'border-transparent bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
        outline: 'text-foreground',
        success: 'border-transparent bg-success text-success-foreground',
        warning: 'border-transparent bg-amber-500 text-white',
        info: 'border-transparent bg-primary/20 text-primary',
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
