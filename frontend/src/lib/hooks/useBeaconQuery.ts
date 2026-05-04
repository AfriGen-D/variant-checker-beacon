'use client';

import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { beaconApi } from '../api/beacon';
import type {
  BeaconResponse,
  BeaconInfo,
  VariantQuery,
  GenomicVariant,
  Individual,
  Biosample,
  Dataset,
  Cohort,
  Analysis,
  FilteringTerm,
} from '../api/types';

/**
 * Hook to get Beacon information
 */
export function useBeaconInfo(): UseQueryResult<BeaconInfo, Error> {
  return useQuery({
    queryKey: ['beacon', 'info'],
    queryFn: () => beaconApi.getInfo(),
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
  });
}

/**
 * Hook to get Beacon configuration
 */
export function useBeaconConfiguration(): UseQueryResult<unknown, Error> {
  return useQuery({
    queryKey: ['beacon', 'configuration'],
    queryFn: () => beaconApi.getConfiguration(),
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
  });
}

/**
 * Hook to get Beacon health status
 */
export function useBeaconHealth(): UseQueryResult<{ status: string }, Error> {
  return useQuery({
    queryKey: ['beacon', 'health'],
    queryFn: () => beaconApi.getHealth(),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refetch every minute
  });
}

/**
 * Hook to query genomic variants
 * @param query - Variant query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useVariantQuery(
  query: VariantQuery,
  enabled = true
): UseQueryResult<BeaconResponse<GenomicVariant>, Error> {
  return useQuery({
    queryKey: ['variants', query],
    queryFn: () => beaconApi.queryVariants(query),
    enabled: enabled && !!query.referenceName && !!query.assemblyId,
    staleTime: 5 * 60 * 1000, // 5 min (matches backend cache TTL)
    gcTime: 10 * 60 * 1000, // 10 min
  });
}

/**
 * Hook to get a single variant by ID
 * @param variantId - Variant identifier
 * @param enabled - Whether the query should be enabled
 */
export function useVariantById(
  variantId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<GenomicVariant>, Error> {
  return useQuery({
    queryKey: ['variants', variantId],
    queryFn: () => beaconApi.getVariantById(variantId!),
    enabled: enabled && !!variantId,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to query individuals
 * @param params - Query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useIndividuals(
  params?: Record<string, string>,
  enabled = true
): UseQueryResult<BeaconResponse<Individual>, Error> {
  return useQuery({
    queryKey: ['individuals', params],
    queryFn: () => beaconApi.queryIndividuals(params),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to get a single individual by ID
 * @param individualId - Individual identifier
 * @param enabled - Whether the query should be enabled
 */
export function useIndividualById(
  individualId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<Individual>, Error> {
  return useQuery({
    queryKey: ['individuals', individualId],
    queryFn: () => beaconApi.getIndividualById(individualId!),
    enabled: enabled && !!individualId,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to query biosamples
 * @param params - Query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useBiosamples(
  params?: Record<string, string>,
  enabled = true
): UseQueryResult<BeaconResponse<Biosample>, Error> {
  return useQuery({
    queryKey: ['biosamples', params],
    queryFn: () => beaconApi.queryBiosamples(params),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to get a single biosample by ID
 * @param biosampleId - Biosample identifier
 * @param enabled - Whether the query should be enabled
 */
export function useBiosampleById(
  biosampleId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<Biosample>, Error> {
  return useQuery({
    queryKey: ['biosamples', biosampleId],
    queryFn: () => beaconApi.getBiosampleById(biosampleId!),
    enabled: enabled && !!biosampleId,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to query datasets
 * @param params - Query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useDatasets(
  params?: Record<string, string>,
  enabled = true
): UseQueryResult<BeaconResponse<Dataset>, Error> {
  return useQuery({
    queryKey: ['datasets', params],
    queryFn: () => beaconApi.queryDatasets(params),
    enabled,
    staleTime: 60 * 60 * 1000, // 1 hour (datasets change rarely)
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
  });
}

/**
 * Hook to get a single dataset by ID
 * @param datasetId - Dataset identifier
 * @param enabled - Whether the query should be enabled
 */
export function useDatasetById(
  datasetId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<Dataset>, Error> {
  return useQuery({
    queryKey: ['datasets', datasetId],
    queryFn: () => beaconApi.getDatasetById(datasetId!),
    enabled: enabled && !!datasetId,
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

/**
 * Hook to query cohorts
 * @param params - Query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useCohorts(
  params?: Record<string, string>,
  enabled = true
): UseQueryResult<BeaconResponse<Cohort>, Error> {
  return useQuery({
    queryKey: ['cohorts', params],
    queryFn: () => beaconApi.queryCohorts(params),
    enabled,
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

/**
 * Hook to get a single cohort by ID
 * @param cohortId - Cohort identifier
 * @param enabled - Whether the query should be enabled
 */
export function useCohortById(
  cohortId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<Cohort>, Error> {
  return useQuery({
    queryKey: ['cohorts', cohortId],
    queryFn: () => beaconApi.getCohortById(cohortId!),
    enabled: enabled && !!cohortId,
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

/**
 * Hook to query analyses
 * @param params - Query parameters
 * @param enabled - Whether the query should be enabled
 */
export function useAnalyses(
  params?: Record<string, string>,
  enabled = true
): UseQueryResult<BeaconResponse<Analysis>, Error> {
  return useQuery({
    queryKey: ['analyses', params],
    queryFn: () => beaconApi.queryAnalyses(params),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to get a single analysis by ID
 * @param analysisId - Analysis identifier
 * @param enabled - Whether the query should be enabled
 */
export function useAnalysisById(
  analysisId: string | null,
  enabled = true
): UseQueryResult<BeaconResponse<Analysis>, Error> {
  return useQuery({
    queryKey: ['analyses', analysisId],
    queryFn: () => beaconApi.getAnalysisById(analysisId!),
    enabled: enabled && !!analysisId,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to get filtering terms
 * @param enabled - Whether the query should be enabled
 */
export function useFilteringTerms(
  enabled = true
): UseQueryResult<BeaconResponse<FilteringTerm>, Error> {
  return useQuery({
    queryKey: ['filteringTerms'],
    queryFn: () => beaconApi.getFilteringTerms(),
    enabled,
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
  });
}
