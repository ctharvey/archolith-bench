import { useState, useEffect } from 'react';
import { apiClient } from '@/data/apiClient';
import type { PromoCard } from './types';

interface UsePromosDataResult {
  promos: PromoCard[];
  loading: boolean;
  error: string | null;
}

export function usePromosData(): UsePromosDataResult {
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
          setError(err instanceof Error ? err.message : 'Failed to load promos');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchPromos();

    return () => {
      cancelled = true;
    };
  }, []);

  return { promos, loading, error };
}
