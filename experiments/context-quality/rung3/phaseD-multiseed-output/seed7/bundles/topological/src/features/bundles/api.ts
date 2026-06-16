import { api } from '@/data/apiClient';
import type { BundlesApiResponse } from './types';

/**
 * Fetch all active product bundles.
 * GET /api/bundles
 */
export async function fetchBundles(): Promise<BundlesApiResponse> {
  const response = await api.get('/api/bundles');
  return response.json();
}
