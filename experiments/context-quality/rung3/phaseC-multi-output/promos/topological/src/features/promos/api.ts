import { api } from '@/data/apiClient';
import type { PromosPageData, PromoCard } from './types';

/** Fetch all promo cards from the API */
export async function fetchPromos(): Promise<PromosPageData> {
  const response = await api.get<PromoCard[]>('/promos');
  return {
    promos: response.data,
    totalCount: response.data.length,
  };
}
