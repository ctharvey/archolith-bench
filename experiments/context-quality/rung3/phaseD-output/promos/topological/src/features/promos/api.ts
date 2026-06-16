import { api } from '@/data/apiClient';
import type { PromoCard } from './types';

/** Fetch all promo cards from the API */
export async function fetchPromos(): Promise<PromoCard[]> {
  const response = await api.get('/promos');
  return response.json();
}
