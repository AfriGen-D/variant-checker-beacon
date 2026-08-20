import type { AssemblyId, Chromosome } from '../api/types';

// Genome assemblies.
//
// Only builds this beacon actually holds. GRCh37 was offered here while the
// panel held none, so a user reached it in two clicks and got an authoritative
// "not in the African panel" for every query — indistinguishable from a true
// negative. The API now refuses an unheld build with 501 rather than answering
// "no" (see beacon_api/capabilities.py), and this list must not re-advertise
// one ahead of the data.
//
// The API is the source of truth: it derives coverage from the dataset
// catalogue. Add a build here only once a dataset declaring it is loaded.
export const ASSEMBLIES: { value: AssemblyId; label: string }[] = [
  { value: 'GRCh38', label: 'GRCh38 (hg38)' },
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

// Validation constants — the single source of truth for coordinate bounds on
// the client. They mirror the backend caps in beacon_api/validators.py
// (GenomicCoordinateValidator): anything the client lets through that the
// server rejects surfaces as a 400 only after the user submits.
export const MAX_GENOMIC_POSITION = 300000000; // validators.py MAX_COORDINATE
// Positions are entered 1-based (converted to 0-based at the API boundary), so
// the floor is 1 — a 0 would be sent as start=-1.
export const MIN_GENOMIC_POSITION = 1;
// validators.py MAX_RANGE, measured against the range the API receives, which
// equals the inclusive base count of a 1-based region (end - start + 1).
export const MAX_REGION_SPAN = 10_000_000;

// Query parameter defaults
export const DEFAULT_ASSEMBLY = 'GRCh38';

// Query modes surfaced as tabs. `available: false` renders the tab disabled
// with a "soon" marker (the Gene tab ships once the /genes resolver lands).
export type QueryMode = 'variant' | 'region' | 'gene';

export const QUERY_MODES: { value: QueryMode; label: string; description: string; available: boolean }[] = [
  { value: 'variant', label: 'Variant', description: 'Exact change at one position (ref → alt)', available: true },
  { value: 'region', label: 'Region', description: 'Any variant overlapping a coordinate range', available: true },
  { value: 'gene', label: 'Gene', description: 'Look up by gene symbol (e.g. BRCA1)', available: false },
];

// Plain-language help shown via the ⓘ next to each field label. Centralized so
// the wording (genomics domain copy) lives in one editable place.
export const FIELD_HINTS = {
  assembly: 'Reference genome build the coordinates refer to. This beacon holds GRCh38 (hg38) data only.',
  chromosome: 'Chromosome the variant sits on (1–22, X, Y, or mitochondrial MT).',
  start: '1-based position, as shown in dbSNP, Ensembl and ClinVar — the exact base for a single-nucleotide variant.',
  end: 'Only needed for a range query. Leave blank for a single-position variant.',
  ref: 'Reference allele — the base(s) in the reference genome (A, C, G, T or N).',
  alt: 'Alternate allele — the observed base(s) you are checking for.',
  regionStart: '1-based start of the region to scan.',
  regionEnd: `1-based end of the region. A region is capped at ${MAX_REGION_SPAN.toLocaleString()} bases.`,
  gene: 'Type a gene symbol (e.g. BRCA1). It is resolved to genomic coordinates and that region is scanned.',
  datasets: 'Which reference panels to query. All are included by default.',
  filters: 'Optional ontology filters (e.g. a gene or phenotype term) to narrow the query.',
} as const;

// Example region queries (range over a locus, no specific allele).
export const REGION_EXAMPLES = [
  { label: 'HBB locus', description: 'Beta-globin region on Chr 11', query: { assemblyId: 'GRCh38', referenceName: '11', start: 5225000, end: 5229000 } },
  { label: 'BRCA1 exon', description: 'A BRCA1 stretch on Chr 17', query: { assemblyId: 'GRCh38', referenceName: '17', start: 43044000, end: 43045000 } },
] as const;

// Example queries for quick discovery. Positions are 1-based (the convention
// used by dbSNP, Ensembl, ClinVar, AGVD); the API client converts to 0-based
// half-open before calling the Beacon endpoint.
export const EXAMPLE_QUERIES = [
  // YES — variants confirmed in the database
  { label: 'HBB G>A', description: 'HBB gene variant on Chr 11', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '11', start: 5225059, end: undefined, referenceBases: 'G', alternateBases: 'A' } },
  { label: 'BRCA1 A>G', description: 'BRCA1 gene variant on Chr 17', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '17', start: 43044127, end: undefined, referenceBases: 'A', alternateBases: 'G' } },
  { label: 'CYP2D6 C>T', description: 'Drug metabolism variant on Chr 22', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '22', start: 42126022, end: undefined, referenceBases: 'C', alternateBases: 'T' } },
  { label: 'CYP2B6 G>T', description: 'Efavirenz metabolism variant on Chr 19', expected: 'yes' as const, query: { assemblyId: 'GRCh38', referenceName: '19', start: 41497060, end: undefined, referenceBases: 'G', alternateBases: 'T' } },
  // NO — positions/alleles not in our dataset
  { label: 'APOE T>C', description: 'Alzheimer risk variant on Chr 19', expected: 'no' as const, query: { assemblyId: 'GRCh38', referenceName: '19', start: 44908685, end: undefined, referenceBases: 'T', alternateBases: 'C' } },
  { label: 'CFTR A>G', description: 'Cystic fibrosis variant on Chr 7', expected: 'no' as const, query: { assemblyId: 'GRCh38', referenceName: '7', start: 117559591, end: undefined, referenceBases: 'A', alternateBases: 'G' } },
] as const;
