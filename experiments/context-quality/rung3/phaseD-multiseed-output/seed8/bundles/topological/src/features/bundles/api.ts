import { api } from '@/data/apiClient';
import type { BundlesApiResponse } from './types';

/**
 * Fetch all active bundles from the API.
 * GET /api/bundles
 */
export async function fetchBundles(): Promise<BundlesApiResponse> {
  return api.get<BundlesApiResponse>('/bundles');
}
