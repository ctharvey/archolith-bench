import { api } from '@/data/apiClient';
import type { PromosPageData } from './types';

/**
 * Load promo cards data from the API.
 * GET /api/promos
 */
export async function loadPromosData(): Promise<PromosPageData> {
  const response = await api.get('/api/promos');
  const data = await response.json();
  
  return {
    promos: data.promos.map((p: any) => ({
      id: p.id,
      name: p.name,
      releaseYear: p.releaseYear,
      imageUrl: p.imageUrl ?? null,
      source: p.source ?? '',
      fmv: p.fmv ?? null,
      d7: p.d7 ?? null,
      d30: p.d30 ?? null,
      d90: p.d90 ?? null,
    })),
    totalCount: data.totalCount ?? data.promos.length,
  };
}
