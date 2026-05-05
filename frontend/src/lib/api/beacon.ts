import { beaconClient } from './client';
import type {
  BeaconResponse,
  BeaconInfo,
  VariantQuery,
  GenomicVariant,
  Individual,
  Biosample,
  Dataset,
  DatasetsListResponse,
  Cohort,
  Analysis,
  FilteringTerm,
} from './types';

/**
 * Beacon API Client
 * Functions for interacting with the GA4GH Beacon v2 API
 */
export const beaconApi = {
  /**
   * Get Beacon information
   * @returns Beacon info object
   */
  getInfo: async (): Promise<BeaconInfo> => {
    const response = await beaconClient.get<BeaconInfo>('/');
    return response.data;
  },

  /**
   * Get service info (GA4GH standard)
   * @returns Service info object
   */
  getServiceInfo: async (): Promise<unknown> => {
    const response = await beaconClient.get('/service-info');
    return response.data;
  },

  /**
   * Get Beacon configuration
   * @returns Configuration object
   */
  getConfiguration: async (): Promise<unknown> => {
    const response = await beaconClient.get('/configuration');
    return response.data;
  },

  /**
   * Get available entry types
   * @returns Entry types object
   */
  getEntryTypes: async (): Promise<unknown> => {
    const response = await beaconClient.get('/entry_types');
    return response.data;
  },

  /**
   * Get endpoint map
   * @returns Map of available endpoints
   */
  getMap: async (): Promise<unknown> => {
    const response = await beaconClient.get('/map');
    return response.data;
  },

  /**
   * Health check
   * @returns Health status
   */
  getHealth: async (): Promise<{ status: string }> => {
    const response = await beaconClient.get<{ status: string }>('/health');
    return response.data;
  },

  /**
   * Query genomic variants (GET)
   * @param query - Variant query parameters (start/end as 1-based inclusive,
   *               matching dbSNP/Ensembl/ClinVar). Converted to Beacon v2's
   *               0-based half-open coordinates at this boundary.
   * @returns Beacon response with variant results
   */
  queryVariants: async (query: VariantQuery): Promise<BeaconResponse<GenomicVariant>> => {
    const params = new URLSearchParams();

    // Beacon v2 spec uses 0-based half-open coordinates. The UI/URL accepts
    // 1-based positions (the convention every public variant database uses)
    // and we convert here. start_0 = start_1 - 1; end stays the same because
    // 1-based inclusive end equals 0-based exclusive end.
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      const out = key === 'start' ? Number(value) - 1 : value;
      params.append(key, out.toString());
    });

    const response = await beaconClient.get(`/g_variants?${params.toString()}`);
    const raw = response.data as any;

    // Normalize flat Boolean-mode response into GA4GH v2 wrapper
    if (raw.response) return raw as BeaconResponse<GenomicVariant>;
    const exists = raw.exists ?? false;
    return {
      meta: { apiVersion: raw.apiVersion ?? 'v2.0.0', beaconId: raw.beaconId ?? '', timestamp: new Date().toISOString() },
      response: {
        exists,
        numTotalResults: exists ? 1 : 0,
        datasetAlleleResponses: raw.datasetAlleleResponses ?? (exists ? [
          { datasetId: 'H3A_V6_AFRICAN', datasetName: 'H3A V6 African Reference Panel', exists: true },
        ] : [
          { datasetId: 'H3A_V6_AFRICAN', datasetName: 'H3A V6 African Reference Panel', exists: false },
        ]),
      },
    };
  },

  /**
   * Query genomic variants (POST)
   * @param query - Variant query object
   * @returns Beacon response with variant results
   */
  queryVariantsPost: async (query: VariantQuery): Promise<BeaconResponse<GenomicVariant>> => {
    const response = await beaconClient.post<BeaconResponse<GenomicVariant>>('/g_variants', {
      query,
    });
    return response.data;
  },

  /**
   * Get single genomic variant by ID
   * @param variantId - Variant identifier
   * @returns Beacon response with variant
   */
  getVariantById: async (variantId: string): Promise<BeaconResponse<GenomicVariant>> => {
    const response = await beaconClient.get<BeaconResponse<GenomicVariant>>(
      `/g_variants/${variantId}`
    );
    return response.data;
  },

  /**
   * Query individuals
   * @param params - Query parameters
   * @returns Beacon response with individuals
   */
  queryIndividuals: async (params?: Record<string, string>): Promise<BeaconResponse<Individual>> => {
    const searchParams = new URLSearchParams(params);
    const response = await beaconClient.get<BeaconResponse<Individual>>(
      `/individuals?${searchParams.toString()}`
    );
    return response.data;
  },

  /**
   * Get single individual by ID
   * @param individualId - Individual identifier
   * @returns Beacon response with individual
   */
  getIndividualById: async (individualId: string): Promise<BeaconResponse<Individual>> => {
    const response = await beaconClient.get<BeaconResponse<Individual>>(
      `/individuals/${individualId}`
    );
    return response.data;
  },

  /**
   * Query biosamples
   * @param params - Query parameters
   * @returns Beacon response with biosamples
   */
  queryBiosamples: async (params?: Record<string, string>): Promise<BeaconResponse<Biosample>> => {
    const searchParams = new URLSearchParams(params);
    const response = await beaconClient.get<BeaconResponse<Biosample>>(
      `/biosamples?${searchParams.toString()}`
    );
    return response.data;
  },

  /**
   * Get single biosample by ID
   * @param biosampleId - Biosample identifier
   * @returns Beacon response with biosample
   */
  getBiosampleById: async (biosampleId: string): Promise<BeaconResponse<Biosample>> => {
    const response = await beaconClient.get<BeaconResponse<Biosample>>(`/biosamples/${biosampleId}`);
    return response.data;
  },

  /**
   * Query datasets
   * @param params - Query parameters
   * @returns Beacon response with datasets
   */
  queryDatasets: async (params?: Record<string, string>): Promise<BeaconResponse<Dataset>> => {
    const searchParams = new URLSearchParams(params);
    const response = await beaconClient.get<BeaconResponse<Dataset>>(
      `/datasets?${searchParams.toString()}`
    );
    return response.data;
  },

  /**
   * Get single dataset by ID
   * @param datasetId - Dataset identifier
   * @returns Beacon response with dataset
   */
  getDatasetById: async (datasetId: string): Promise<BeaconResponse<Dataset>> => {
    const response = await beaconClient.get<BeaconResponse<Dataset>>(`/datasets/${datasetId}`);
    return response.data;
  },

  /**
   * Query cohorts
   * @param params - Query parameters
   * @returns Beacon response with cohorts
   */
  queryCohorts: async (params?: Record<string, string>): Promise<BeaconResponse<Cohort>> => {
    const searchParams = new URLSearchParams(params);
    const response = await beaconClient.get<BeaconResponse<Cohort>>(
      `/cohorts?${searchParams.toString()}`
    );
    return response.data;
  },

  /**
   * Get single cohort by ID
   * @param cohortId - Cohort identifier
   * @returns Beacon response with cohort
   */
  getCohortById: async (cohortId: string): Promise<BeaconResponse<Cohort>> => {
    const response = await beaconClient.get<BeaconResponse<Cohort>>(`/cohorts/${cohortId}`);
    return response.data;
  },

  /**
   * Query analyses
   * @param params - Query parameters
   * @returns Beacon response with analyses
   */
  queryAnalyses: async (params?: Record<string, string>): Promise<BeaconResponse<Analysis>> => {
    const searchParams = new URLSearchParams(params);
    const response = await beaconClient.get<BeaconResponse<Analysis>>(
      `/analyses?${searchParams.toString()}`
    );
    return response.data;
  },

  /**
   * Get single analysis by ID
   * @param analysisId - Analysis identifier
   * @returns Beacon response with analysis
   */
  getAnalysisById: async (analysisId: string): Promise<BeaconResponse<Analysis>> => {
    const response = await beaconClient.get<BeaconResponse<Analysis>>(`/analyses/${analysisId}`);
    return response.data;
  },

  /**
   * Get filtering terms
   * @returns Beacon response with filtering terms
   */
  getFilteringTerms: async (): Promise<BeaconResponse<FilteringTerm>> => {
    const response = await beaconClient.get<BeaconResponse<FilteringTerm>>('/filtering_terms');
    return response.data;
  },

  /**
   * Get all datasets (Boolean mode)
   * @returns Datasets list with variant counts
   */
  getDatasets: async (): Promise<DatasetsListResponse> => {
    const response = await beaconClient.get<DatasetsListResponse>('/datasets');
    return response.data;
  },
};

// Export individual functions for convenience
export const {
  getInfo,
  getServiceInfo,
  getConfiguration,
  getEntryTypes,
  getMap,
  getHealth,
  queryVariants,
  queryVariantsPost,
  getVariantById,
  queryIndividuals,
  getIndividualById,
  queryBiosamples,
  getBiosampleById,
  queryDatasets,
  getDatasetById,
  queryCohorts,
  getCohortById,
  queryAnalyses,
  getAnalysisById,
  getFilteringTerms,
  getDatasets,
} = beaconApi;
