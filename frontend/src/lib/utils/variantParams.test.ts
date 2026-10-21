import { describe, expect, it } from '@jest/globals';
import { variantQueryParams } from './variantParams';
import type { VariantQuery } from '@/lib/api/types';

const q = (over: Partial<VariantQuery> = {}): VariantQuery => ({
  assemblyId: 'GRCh38',
  referenceName: '11',
  start: 5225059,
  referenceBases: 'G',
  alternateBases: 'A',
  ...over,
});

describe('variantQueryParams', () => {
  it('sends the 0-based start: the 1-based position minus one', () => {
    expect(variantQueryParams(q()).get('start')).toBe('5225058');
  });

  it('leaves end unchanged (1-based inclusive end equals 0-based exclusive end)', () => {
    expect(variantQueryParams(q({ end: 5225100 })).get('end')).toBe('5225100');
  });

  it('always requests aggregated granularity', () => {
    expect(variantQueryParams(q()).get('requestedGranularity')).toBe('aggregated');
  });

  it('keeps an explicitly requested granularity', () => {
    const p = variantQueryParams({ ...q(), requestedGranularity: 'record' } as VariantQuery);
    expect(p.getAll('requestedGranularity')).toEqual(['record']);
  });

  it('drops empty, null and undefined fields', () => {
    const p = variantQueryParams(q({ referenceBases: '', alternateBases: undefined }));
    expect(p.has('referenceBases')).toBe(false);
    expect(p.has('alternateBases')).toBe(false);
  });

  it('converts start 1 to 0, the lowest valid position', () => {
    expect(variantQueryParams(q({ start: 1 })).get('start')).toBe('0');
  });

  it('matches the request the live UI sent for chr11:5225059 G>A', () => {
    expect(variantQueryParams(q()).toString()).toBe(
      'assemblyId=GRCh38&referenceName=11&start=5225058&referenceBases=G&alternateBases=A&requestedGranularity=aggregated'
    );
  });
});
