import { api } from '@/data/apiClient';
import type { PromosPageData } from './types';

/**
 * Fetch all promo cards from the API.
 * GET /api/promos
 */
export async function fetchPromos(): Promise<PromosPageData> {
  const response = await api.get('/api/promos');
  const data = await response.json();
  return {
    promos: data.promos ?? [],
    totalCount: data.totalCount ?? 0,
  };
}
