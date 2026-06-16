import { api } from '@/data/apiClient';
import type { BundlesPageData } from './types';

/**
 * Fetch all active bundles from the API.
 * GET /api/bundles
 */
export async function fetchBundles(): Promise<BundlesPageData> {
  const response = await api.get('/api/bundles');
  const data = await response.json();
  return {
    bundles: data.bundles ?? [],
    totalBundles: data.totalBundles ?? 0,
  };
}
