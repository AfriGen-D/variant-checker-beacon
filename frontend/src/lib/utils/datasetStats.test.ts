import { describe, expect, it } from '@jest/globals';
import { formatDatasetDate, summariseDatasets } from './datasetStats';
import type { Dataset } from '@/lib/api/types';

const ds = (over: Partial<Dataset> = {}): Dataset => ({ id: 'a', name: 'A', ...over });

describe('summariseDatasets', () => {
  it('reports an empty list as zero datasets and unknown totals, not zero variants', () => {
    const s = summariseDatasets([]);
    expect(s.datasetCount).toBe(0);
    expect(s.variantCount).toBeNull();
    expect(s.sampleCount).toBeNull();
    expect(s.assemblies).toEqual([]);
    expect(s.updated).toBeNull();
  });

  it('passes a single dataset through', () => {
    const s = summariseDatasets([
      ds({
        variantCount: 42331932,
        sampleCount: 1895,
        assemblyId: 'GRCh38',
        updateDateTime: '2026-05-06T10:00:00Z',
      }),
    ]);
    expect(s.datasetCount).toBe(1);
    expect(s.variantCount).toBe(42331932);
    expect(s.sampleCount).toBe(1895);
    expect(s.assemblies).toEqual(['GRCh38']);
    expect(s.updated?.toISOString()).toBe('2026-05-06T10:00:00.000Z');
  });

  it('sums counts across datasets', () => {
    const s = summariseDatasets([
      ds({ id: 'a', variantCount: 10, sampleCount: 2 }),
      ds({ id: 'b', variantCount: 5, sampleCount: 3 }),
    ]);
    expect(s.variantCount).toBe(15);
    expect(s.sampleCount).toBe(5);
  });

  it('makes a total unknown when any dataset does not report that count', () => {
    const s = summariseDatasets([
      ds({ id: 'a', variantCount: 10, sampleCount: 2 }),
      ds({ id: 'b', sampleCount: 3 }),
    ]);
    expect(s.variantCount).toBeNull();
    expect(s.sampleCount).toBe(5);
  });

  it('keeps a real zero distinct from an unknown count', () => {
    expect(summariseDatasets([ds({ variantCount: 0 })]).variantCount).toBe(0);
  });

  it('rejects negative and non-finite counts as unknown', () => {
    expect(summariseDatasets([ds({ variantCount: -1 })]).variantCount).toBeNull();
    expect(summariseDatasets([ds({ variantCount: Number.NaN })]).variantCount).toBeNull();
  });

  it('lists each assembly once, in first-seen order, skipping missing ones', () => {
    const s = summariseDatasets([
      ds({ id: 'a', assemblyId: 'GRCh38' }),
      ds({ id: 'b' }),
      ds({ id: 'c', assemblyId: 'GRCh37' }),
      ds({ id: 'd', assemblyId: 'GRCh38' }),
    ]);
    expect(s.assemblies).toEqual(['GRCh38', 'GRCh37']);
  });

  it('takes the latest date, falls back to creation time, and ignores unparseable dates', () => {
    const s = summariseDatasets([
      ds({ id: 'a', updateDateTime: '2026-01-01T00:00:00Z' }),
      ds({ id: 'b', createDateTime: '2026-03-01T00:00:00Z' }),
      ds({ id: 'c', updateDateTime: 'not a date' }),
    ]);
    expect(s.updated?.toISOString()).toBe('2026-03-01T00:00:00.000Z');
  });

  it('returns null when no dataset has a usable date', () => {
    expect(summariseDatasets([ds({ updateDateTime: 'nope' }), ds({ id: 'b' })]).updated).toBeNull();
  });
});

describe('formatDatasetDate', () => {
  it('formats in UTC so the day does not shift with the viewer timezone', () => {
    expect(formatDatasetDate(new Date('2026-05-06T23:30:00Z'))).toBe('6 May 2026');
  });
});
