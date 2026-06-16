import { useState, useEffect } from 'react';
import { apiClient } from '@/data/apiClient';
import type { PromoCard } from './types';

export function usePromosData() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchPromos() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.get<PromoCard[]>('/api/pokemon/cards/promos');
        if (!cancelled) {
          setPromos(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load promo cards');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    fetchPromos();
    return () => { cancelled = true; };
  }, []);

  return { promos, loading, error };
}
