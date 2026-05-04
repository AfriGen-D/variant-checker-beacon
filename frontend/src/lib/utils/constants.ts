import type { AssemblyId, Chromosome } from '../api/types';

// Genome assemblies
export const ASSEMBLIES: { value: AssemblyId; label: string }[] = [
  { value: 'GRCh38', label: 'GRCh38 (hg38)' },
  { value: 'GRCh37', label: 'GRCh37 (hg19)' },
];

// Chromosomes
export const CHROMOSOMES: { value: Chromosome; label: string }[] = [
  { value: '1', label: 'Chr 1' },
  { value: '2', label: 'Chr 2' },
  { value: '3', label: 'Chr 3' },
  { value: '4', label: 'Chr 4' },
  { value: '5', label: 'Chr 5' },
  { value: '6', label: 'Chr 6' },
  { value: '7', label: 'Chr 7' },
  { value: '8', label: 'Chr 8' },
  { value: '9', label: 'Chr 9' },
  { value: '10', label: 'Chr 10' },
  { value: '11', label: 'Chr 11' },
  { value: '12', label: 'Chr 12' },
  { value: '13', label: 'Chr 13' },
  { value: '14', label: 'Chr 14' },
  { value: '15', label: 'Chr 15' },
  { value: '16', label: 'Chr 16' },
  { value: '17', label: 'Chr 17' },
  { value: '18', label: 'Chr 18' },
  { value: '19', label: 'Chr 19' },
  { value: '20', label: 'Chr 20' },
  { value: '21', label: 'Chr 21' },
  { value: '22', label: 'Chr 22' },
  { value: 'X', label: 'Chr X' },
  { value: 'Y', label: 'Chr Y' },
  { value: 'MT', label: 'Chr MT (Mitochondrial)' },
];

// Nucleotide bases
export const BASES = ['A', 'T', 'G', 'C', 'N'] as const;

// Validation constants
export const MAX_GENOMIC_POSITION = 3000000000;
export const MIN_GENOMIC_POSITION = 0;

// Query parameter defaults
export const DEFAULT_ASSEMBLY = 'GRCh38';

// Example queries for quick discovery (verified against H3A V6 African panel, GRCh38)
export const EXAMPLE_QUERIES = [
  // YES — variants confirmed in the database
  { label: 'HBB G>A', description: 'HBB gene variant on Chr 11', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '11', start: 5225058, end: undefined, referenceBases: 'G', alternateBases: 'A' } },
  { label: 'BRCA1 A>G', description: 'BRCA1 gene variant on Chr 17', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '17', start: 43044126, end: undefined, referenceBases: 'A', alternateBases: 'G' } },
  { label: 'CYP2D6 C>T', description: 'Drug metabolism variant on Chr 22', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '22', start: 42126021, end: undefined, referenceBases: 'C', alternateBases: 'T' } },
  { label: 'CYP2B6 G>T', description: 'Efavirenz metabolism variant on Chr 19', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '19', start: 41497059, end: undefined, referenceBases: 'G', alternateBases: 'T' } },
  // NO — positions/alleles not in our dataset
  { label: 'APOE T>C', description: 'Alzheimer risk variant on Chr 19', expected: 'no' as const, query: { assemblyId: 'GRCh38', referenceName: '19', start: 44908684, end: undefined, referenceBases: 'T', alternateBases: 'C' } },
  { label: 'CFTR A>G', description: 'Cystic fibrosis variant on Chr 7', expected: 'no' as const, query: { assemblyId: 'GRCh38', referenceName: '7', start: 117559590, end: undefined, referenceBases: 'A', alternateBases: 'G' } },
] as const;
