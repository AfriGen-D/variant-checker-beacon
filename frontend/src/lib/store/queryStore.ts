import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { VariantQuery, BeaconResponse, GenomicVariant } from '../api/types';

export interface QueryHistoryItem {
  query: VariantQuery;
  timestamp: string;
  result?: BeaconResponse<GenomicVariant>;
}

interface QueryStore {
  queryHistory: QueryHistoryItem[];
  currentQuery: VariantQuery | null;
  addQuery: (query: VariantQuery, result?: BeaconResponse<GenomicVariant>) => void;
  clearHistory: () => void;
  setCurrentQuery: (query: VariantQuery | null) => void;
}

export const useQueryStore = create<QueryStore>()(
  persist(
    (set) => ({
      queryHistory: [],
      currentQuery: null,

      addQuery: (query, result) =>
        set((state) => ({
          queryHistory: [
            {
              query,
              result,
              timestamp: new Date().toISOString(),
            },
            ...state.queryHistory,
          ].slice(0, 10), // Keep only last 10 queries
        })),

      clearHistory: () => set({ queryHistory: [] }),

      setCurrentQuery: (query) => set({ currentQuery: query }),
    }),
    {
      name: 'beacon-query-history',
    }
  )
);
