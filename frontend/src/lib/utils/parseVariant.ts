import type { VariantQueryFormData } from './validators';
import { CHROMOSOMES, BASES, DEFAULT_ASSEMBLY } from './constants';

const VALID_CHROMOSOMES = new Set(CHROMOSOMES.map((c) => c.value as string));
const VALID_BASES = new Set<string>(BASES);

export interface ParsedVariant {
  /** Partial form data extracted from the string (assembly defaulted). */
  data: Partial<VariantQueryFormData>;
  /** True when chromosome, start, ref and alt were all recovered. */
  complete: boolean;
}

export interface ParseResult {
  ok: boolean;
  parsed?: ParsedVariant;
  error?: string;
}

/**
 * Normalise a chromosome token to the bare Beacon form ("1", "X", "MT").
 * Accepts "chr11", "CHR11", "11", "chrM"/"M" → "MT". Returns null if unknown.
 */
function normaliseChromosome(token: string): string | null {
  let chr = token.trim().toUpperCase();
  if (chr.startsWith('CHR')) chr = chr.slice(3);
  if (chr === 'M' || chr === 'MT') chr = 'MT';
  return VALID_CHROMOSOMES.has(chr) ? chr : null;
}

function isBaseString(token: string): boolean {
  const upper = token.toUpperCase();
  return upper.length > 0 && [...upper].every((c) => VALID_BASES.has(c));
}

/**
 * Parse a free-form variant string into Beacon query fields.
 *
 * Recognised shapes (all 1-based, the convention of dbSNP / Ensembl / gnomAD):
 *   chr11:5225059 G>A      chr11:5225059:G:A     11-5225059-G-A
 *   11:5225059:G:A         11 5225059 G A        chr11:g.5225059G>A
 *   chr11:5225059          (position only — fills chrom + start, no alleles)
 *   11:5225059:5225100     (range — fills chrom + start + end)
 *
 * Strategy: pull a `ref>alt` arrow out first (it survives any glue, e.g.
 * "5225059G>A"), then tokenise the remainder on : - _ and whitespace. The
 * first two tokens are always chromosome and start; the rest are classified
 * by shape — all-digit tokens become an end position, all-base tokens become
 * ref then alt in order.
 */
export function parseVariantString(input: string): ParseResult {
  const raw = input.trim();
  if (!raw) return { ok: false, error: 'Enter a variant to look up' };

  let working = raw;
  let ref: string | undefined;
  let alt: string | undefined;

  // ref>alt notation, e.g. "G>A" — extracted first so glued HGVS like
  // "5225059G>A" still parses (the digits before G aren't bases, so the
  // capture stops at the base run).
  const arrow = working.match(/([ACGTN]+)\s*>\s*([ACGTN]+)/i);
  if (arrow) {
    ref = arrow[1].toUpperCase();
    alt = arrow[2].toUpperCase();
    working = working.replace(arrow[0], ' ');
  }

  // Drop an HGVS "g." prefix, then split on the common variant delimiters.
  const tokens = working
    .replace(/\bg\./i, ' ')
    .split(/[\s:_\-]+/)
    .map((t) => t.trim())
    .filter(Boolean);

  if (tokens.length === 0) {
    return { ok: false, error: 'Could not find a chromosome or position' };
  }

  const referenceName = normaliseChromosome(tokens[0]);
  if (!referenceName) {
    return {
      ok: false,
      error: `"${tokens[0]}" is not a recognised chromosome (use 1–22, X, Y, MT)`,
    };
  }

  const startToken = tokens[1];
  if (!startToken || !/^\d+$/.test(startToken)) {
    return { ok: false, error: 'Could not find a numeric start position' };
  }
  const start = Number(startToken);

  // Classify whatever is left: digits → end position, bases → ref/alt in order.
  let end: number | undefined;
  for (const token of tokens.slice(2)) {
    if (/^\d+$/.test(token)) {
      end = Number(token);
    } else if (isBaseString(token)) {
      if (!ref) ref = token.toUpperCase();
      else if (!alt) alt = token.toUpperCase();
    } else {
      return { ok: false, error: `Could not interpret "${token}"` };
    }
  }

  const data: Partial<VariantQueryFormData> = {
    assemblyId: DEFAULT_ASSEMBLY,
    referenceName,
    start,
    end,
    referenceBases: ref,
    alternateBases: alt,
  };

  const complete = Boolean(referenceName && start && ref && alt);
  return { ok: true, parsed: { data, complete } };
}
