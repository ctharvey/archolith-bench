import { useQuery } from '@tanstack/react-query';
import { fetchBundles } from './api';
import type { Bundle } from './types';

/** React Query key for bundles */
export const bundlesQueryKey = ['bundles'] as const;

/** Hook to fetch and return bundles list */
export function useBundles() {
  return useQuery({
    queryKey: bundlesQueryKey,
    queryFn: fetchBundles,
    select: (data) => data.bundles,
  });
}

/** Hook to fetch a single bundle by ID */
export function useBundle(id: string) {
  return useQuery({
    queryKey: [...bundlesQueryKey, id],
    queryFn: async () => {
      const response = await api.get(`/api/bundles/${id}`);
      return response.json() as Promise<Bundle>;
    },
    enabled: !!id,
  });
}
