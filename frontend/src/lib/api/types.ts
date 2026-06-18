// GA4GH Beacon v2 API TypeScript Interfaces

// Beacon Response Format (Standardized)
export interface BeaconResponse<T = unknown> {
  meta: BeaconMeta;
  response: BeaconResponseContent<T>;
}

export interface BeaconMeta {
  apiVersion: string;
  beaconId: string;
  timestamp: string;
  returnedSchemas?: string[];
  info?: string;
}

export interface BeaconResponseContent<T = unknown> {
  exists: boolean;
  numTotalResults?: number;
  results?: T[];
  info?: BeaconInfo;
  datasetAlleleResponses?: DatasetAlleleResponse[];
  beaconHandovers?: Handover[];
}

export interface DatasetAlleleResponse {
  datasetId: string;
  datasetName: string;
  exists: boolean;
  resultsHandover?: Handover[];
  // Allele frequency lifted from the resultSet's frequencyInPopulations
  // (present at 'aggregated' granularity when the beacon has it).
  alleleFrequency?: number;
}

// GA4GH Beacon v2 frequencyInPopulations (aggregated granularity)
export interface PopulationFrequency {
  population: string;
  alleleFrequency: number;
}

export interface FrequencyInPopulation {
  source: string;
  sourceReference: string;
  frequencies: PopulationFrequency[];
}

export interface Handover {
  handoverType: { id: string; label: string };
  url: string;
  note?: string;
}

export interface BeaconInfo {
  id: string;
  name: string;
  apiVersion: string;
  environment: string;
  organization: BeaconOrganization;
  description?: string;
  version?: string;
  welcomeUrl?: string;
  alternativeUrl?: string;
  createDateTime?: string;
  updateDateTime?: string;
}

export interface BeaconOrganization {
  id: string;
  name: string;
  description?: string;
  address?: string;
  welcomeUrl?: string;
  contactUrl?: string;
  logoUrl?: string;
  info?: Record<string, unknown>;
}

// Genomic Variant Query Parameters
export interface VariantQuery {
  assemblyId: string; // e.g., "GRCh38", "GRCh37"
  referenceName: string; // e.g., "1", "2", "X", "Y", "MT"
  start?: number; // Genomic position (0-based)
  end?: number; // Genomic position (0-based)
  referenceBases?: string; // e.g., "A", "T", "G", "C"
  alternateBases?: string; // e.g., "T", "A", "G", "C"
  variantType?: string; // e.g., "SNP", "DEL", "INS"
  variantMinLength?: number;
  variantMaxLength?: number;
  requestedGranularity?: 'boolean' | 'count' | 'aggregated' | 'record';
}

// Genomic Variant Model
export interface GenomicVariant {
  id: string;
  assemblyId: string;
  referenceName: string;
  start: number;
  end?: number;
  referenceBases: string;
  alternateBases: string;
  variantType?: string;
  info?: Record<string, unknown>;
}

// Individual Model
export interface Individual {
  id: string;
  sex?: string;
  ethnicity?: string;
  geographicOrigin?: string;
  age?: number;
  diseases?: Disease[];
  phenotypicFeatures?: PhenotypicFeature[];
  info?: Record<string, unknown>;
}

export interface Disease {
  diseaseCode: OntologyTerm;
  ageOfOnset?: AgeRange;
  stage?: OntologyTerm;
  familyHistory?: boolean;
}

export interface PhenotypicFeature {
  featureType: OntologyTerm;
  excluded?: boolean;
  modifiers?: OntologyTerm[];
}

export interface OntologyTerm {
  id: string;
  label: string;
}

export interface AgeRange {
  start: Age;
  end?: Age;
}

export interface Age {
  age: string;
}

// Biosample Model
export interface Biosample {
  id: string;
  individualId?: string;
  description?: string;
  sampleType?: string;
  biosampleStatus?: OntologyTerm;
  sampleOriginType?: OntologyTerm;
  collectionDate?: string;
  tissue?: string;
  sampleProcessing?: string;
  materialUsed?: string;
  info?: Record<string, unknown>;
}

// Dataset Model
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  assemblyId?: string;
  variantCount?: number;
  sampleCount?: number;
  createDateTime?: string;
  updateDateTime?: string;
  version?: string;
  externalUrl?: string;
  info?: Record<string, unknown>;
}

export interface DatasetsListResponse {
  datasets: Dataset[];
}

// Cohort Model
export interface Cohort {
  id: string;
  name: string;
  description?: string;
  cohortType?: string;
  cohortDesign?: string;
  cohortSize?: number;
  individualIds?: string[];
  collectionEvents?: CollectionEvent[];
  info?: Record<string, unknown>;
}

export interface CollectionEvent {
  eventNum: number;
  eventDate?: string;
  eventSize?: number;
  eventCases?: number;
  eventControls?: number;
}

// Analysis Model
export interface Analysis {
  id: string;
  biosampleId?: string;
  analysisType?: string;
  analysisDate?: string;
  software?: string;
  softwareVersion?: string;
  pipelineName?: string;
  pipelineVersion?: string;
  pipelineRef?: string;
  info?: Record<string, unknown>;
}

// Filtering Terms
export interface FilteringTerm {
  type: string;
  id: string;
  label?: string;
  scope?: string[];
}

// API Error Response
export interface BeaconError {
  error: {
    errorCode: number;
    errorMessage: string;
  };
}

// Utility Types
export type AssemblyId = 'GRCh37' | 'GRCh38' | 'GRCh38.p13' | string;
export type Chromosome = '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | '10' |
  '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' |
  '21' | '22' | 'X' | 'Y' | 'MT';
export type Base = 'A' | 'T' | 'G' | 'C' | 'N';
