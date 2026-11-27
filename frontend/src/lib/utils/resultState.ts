import type { DatasetCoverage } from '@/lib/api/types';

/**
 * What one dataset's answer establishes. A "no" is only an absence when the
 * dataset says it holds the chromosome asked about.
 */
export type ResultState = 'present' | 'absent' | 'notCovered' | 'unchecked';

// The names the API accepts for a chromosome (beacon_api/capabilities.py).
const CHROMOSOME = /^(?:[1-9]|1\d|2[0-2]|X|Y|MT)$/;

function chromosomeName(referenceName: string): string | undefined {
  const bare = referenceName.trim().replace(/^chr/i, '').toUpperCase();
  const name = bare === 'M' ? 'MT' : bare;
  return CHROMOSOME.test(name) ? name : undefined;
}

export function resultState(
  exists: boolean,
  referenceName: string,
  coverage: DatasetCoverage | undefined,
): ResultState {
  if (exists) return 'present';
  const asked = chromosomeName(referenceName);
  const held = coverage?.chromosomes;
  if (!asked || !held?.length) return 'unchecked';
  return held.some(name => chromosomeName(name) === asked) ? 'absent' : 'notCovered';
}

function buildName(assemblyId: string): string {
  const name = assemblyId.trim().toLowerCase();
  if (name === 'hg38') return 'grch38';
  if (name === 'hg19') return 'grch37';
  return name;
}

/**
 * Coverage describes one genome build. A "no" for a question asked in another
 * build says nothing about the chromosomes the dataset holds.
 */
export function coverageFor(
  dataset: { assemblyId?: string; coverage?: DatasetCoverage } | undefined,
  askedAssembly: string | undefined,
): DatasetCoverage | undefined {
  const held = dataset?.assemblyId;
  if (held && askedAssembly && buildName(held) !== buildName(askedAssembly)) {
    return undefined;
  }
  return dataset?.coverage;
}

export type NegativeVerdict = 'complete' | 'notCovered' | 'incomplete';

/** How much a lookup with no hit establishes across the datasets asked. */
export function negativeVerdict(states: ResultState[]): NegativeVerdict {
  if (states.length === 0) return 'incomplete';
  if (states.every(s => s === 'absent')) return 'complete';
  if (states.every(s => s === 'notCovered')) return 'notCovered';
  return 'incomplete';
}
