import { api } from '@/data/apiClient';
import type { BundlesPageData, Bundle } from './types';

/** Fetch all active bundles from the API */
export async function fetchBundles(): Promise<BundlesPageData> {
  const response = await api.get<Bundle[]>('/bundles');
  const bundles = response.data ?? [];
  return {
    bundles,
    totalBundles: bundles.length,
  };
}
