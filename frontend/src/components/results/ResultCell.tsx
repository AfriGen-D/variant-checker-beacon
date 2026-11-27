import { Check, CircleHelp, CircleSlash, Minus } from 'lucide-react';
import type { ResultState } from '@/lib/utils/resultState';

// Word, icon and pattern together: no state depends on colour alone, and a
// "no" never looks like a "cannot answer".
const STATES = {
  present: {
    label: 'Present',
    sub: 'AF not reported',
    Icon: Check,
    tone: 'border border-affirm/40 bg-affirm-bg text-affirm',
  },
  absent: {
    label: 'Absent',
    sub: 'chromosome covered',
    Icon: Minus,
    tone: 'border bg-card text-quiet',
  },
  notCovered: {
    label: 'Not covered',
    sub: 'chromosome not in dataset',
    Icon: CircleSlash,
    tone: 'border text-quiet bg-[repeating-linear-gradient(135deg,var(--quiet-bg)_0_6px,var(--card)_6px_12px)]',
  },
  unchecked: {
    label: 'No, unchecked',
    sub: 'coverage not reported',
    Icon: CircleHelp,
    tone: 'border-[1.5px] border-dashed border-inert bg-card text-quiet',
  },
} as const;

export function ResultCell({ state, alleleFrequency }: { state: ResultState; alleleFrequency?: number }) {
  const { label, sub, Icon, tone } = STATES[state];
  const detail =
    state === 'present' && alleleFrequency !== undefined ? `AF ${alleleFrequency.toFixed(4)}` : sub;

  return (
    <div className={`flex h-14 w-44 shrink-0 flex-col items-center justify-center gap-0.5 rounded-lg ${tone}`}>
      {/* The solid backing keeps the words readable over the hatched pattern. */}
      <span className="flex items-center gap-1.5 rounded-full px-2 text-sm font-semibold">
        <Icon aria-hidden="true" className="h-4 w-4" />
        {label}
      </span>
      <span className={`rounded px-1 text-[11px] tabular-nums ${state === 'notCovered' ? 'bg-card' : ''}`}>
        {detail}
      </span>
    </div>
  );
}
