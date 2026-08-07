import { Badge } from '@/components/ui/Badge';

interface Props {
  /** Datasets that returned a hit. */
  matched: number;
  /** Datasets actually searched. */
  total: number;
  /** False before any lookup has run. */
  hasQuery: boolean;
}

/**
 * The verdict, stated with its own limits.
 *
 * Ported from the aggregator, where four different truths were previously
 * collapsed into one badge. A single beacon has fewer states than a federation
 * but the same failure mode: "no result" and "nothing was asked" are different
 * claims, and a bare YES/NO cannot tell them apart.
 *
 * The mark is a fraction rather than a word because `0/0` and `0/3` are
 * different glyphs while "No" and "No" are the same one — so a lookup that
 * searched nothing has no valid rendering as a negative result.
 *
 * Each verdict carries a sentence naming what it does and does not establish.
 * That sentence is the point: a researcher quoting this in a methods section
 * needs to know the negative covers these panels at this position, and nothing
 * wider.
 */
export function RecordHead({ matched, total, hasQuery }: Props) {
  if (!hasQuery) {
    return (
      <div className="flex items-start gap-3.5">
        <Badge variant="secondary" size="lg" className="font-mono tabular-nums shrink-0">—</Badge>
        <div className="min-w-0">
          <h3 className="text-lg font-semibold leading-tight">Not queried yet</h3>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Nothing has been asked of this beacon. Deliberately distinct from a
            negative answer — no dataset has been searched.
          </p>
        </div>
      </div>
    );
  }

  const found = matched > 0;
  const nothingSearched = total === 0;

  const variant = nothingSearched ? 'secondary' : found ? 'success' : 'negative';
  const headline = nothingSearched
    ? 'No dataset was searched'
    : found
      ? `Present in ${matched} of ${total} dataset${total === 1 ? '' : 's'}`
      : `Absent from ${total === 1 ? 'the dataset' : `all ${total} datasets`}`;

  const limit = nothingSearched
    ? 'No panel matched this query, so nothing is established either way. This is not a negative result.'
    : found
      ? 'Presence is reported without disclosing which individuals carry the variant. Use the database links below for allele frequencies and clinical detail.'
      : `Every dataset answered and none has it, so this negative is complete for ${total === 1 ? 'this panel' : 'these panels'} at this position. It says nothing about African populations they do not cover.`;

  return (
    <div className="flex items-start gap-3.5">
      <Badge variant={variant} size="lg" className="font-mono tabular-nums shrink-0">
        {matched}/{total}
      </Badge>
      <div className="min-w-0">
        <h3 className="text-lg font-semibold leading-tight" aria-live="polite">{headline}</h3>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{limit}</p>
      </div>
    </div>
  );
}
