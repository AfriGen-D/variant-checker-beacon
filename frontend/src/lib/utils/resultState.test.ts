import { describe, expect, it } from '@jest/globals';
import { coverageFor, negativeVerdict, resultState } from './resultState';

const autosomes = { chromosomes: ['1', '11', '22'], alleleFrequency: false };

describe('resultState', () => {
  it('is present when the dataset holds the variant, whatever coverage says', () => {
    expect(resultState(true, '11', autosomes)).toBe('present');
    expect(resultState(true, 'X', autosomes)).toBe('present');
    expect(resultState(true, '11', undefined)).toBe('present');
  });
  it('is absent when the chromosome is covered and the variant is not there', () => {
    expect(resultState(false, '11', autosomes)).toBe('absent');
  });
  it('is not covered when the dataset does not hold the chromosome', () => {
    expect(resultState(false, 'X', autosomes)).toBe('notCovered');
  });
  it('is unchecked, never not covered, when coverage is not reported', () => {
    expect(resultState(false, 'X', undefined)).toBe('unchecked');
  });
  it('is unchecked for an empty or malformed chromosome list', () => {
    expect(resultState(false, '11', { chromosomes: [], alleleFrequency: false })).toBe('unchecked');
    expect(resultState(false, '11', {} as never)).toBe('unchecked');
    expect(resultState(false, '11', null as never)).toBe('unchecked');
  });
  it('reads chr prefixes, lower case and M as the same chromosome', () => {
    const cov = { chromosomes: ['11', 'X', 'MT'], alleleFrequency: false };
    expect(resultState(false, 'chr11', cov)).toBe('absent');
    expect(resultState(false, 'x', cov)).toBe('absent');
    expect(resultState(false, 'chrM', cov)).toBe('absent');
  });
  it('is unchecked for a reference name it cannot place on a chromosome', () => {
    expect(resultState(false, 'NC_000011.10', autosomes)).toBe('unchecked');
    expect(resultState(false, '23', autosomes)).toBe('unchecked');
    expect(resultState(false, '', autosomes)).toBe('unchecked');
  });
});

describe('coverageFor', () => {
  const dataset = { assemblyId: 'GRCh38', coverage: autosomes };
  it('applies to the build the dataset holds, under either of its names', () => {
    expect(coverageFor(dataset, 'GRCh38')).toBe(autosomes);
    expect(coverageFor(dataset, 'hg38')).toBe(autosomes);
  });
  it('says nothing about another genome build', () => {
    expect(coverageFor(dataset, 'GRCh37')).toBeUndefined();
    expect(coverageFor(dataset, 'hg19')).toBeUndefined();
  });
  it('is kept when either side does not name a build', () => {
    expect(coverageFor(dataset, undefined)).toBe(autosomes);
    expect(coverageFor({ coverage: autosomes }, 'GRCh38')).toBe(autosomes);
  });
  it('is undefined for a dataset that is unknown or unmeasured', () => {
    expect(coverageFor(undefined, 'GRCh38')).toBeUndefined();
    expect(coverageFor({ assemblyId: 'GRCh38' }, 'GRCh38')).toBeUndefined();
  });
});

describe('negativeVerdict', () => {
  it('is complete only when every dataset covers the chromosome', () => {
    expect(negativeVerdict(['absent'])).toBe('complete');
    expect(negativeVerdict(['absent', 'absent'])).toBe('complete');
  });
  it('is not covered when no dataset holds the chromosome', () => {
    expect(negativeVerdict(['notCovered', 'notCovered'])).toBe('notCovered');
  });
  it('is incomplete when any dataset could not answer', () => {
    expect(negativeVerdict(['absent', 'notCovered'])).toBe('incomplete');
    expect(negativeVerdict(['absent', 'unchecked'])).toBe('incomplete');
    expect(negativeVerdict(['unchecked'])).toBe('incomplete');
  });
  it('is never complete over no datasets at all', () => {
    expect(negativeVerdict([])).toBe('incomplete');
  });
});
