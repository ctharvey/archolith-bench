import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';

export interface PromoSet {
  id: string;
  name: string;
  code: string;
  serie: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
}

interface PromoApiResponse {
  promos: PromoSet[];
}

export function usePromosData() {
  const [promos, setPromos] = useState<PromoSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPromos() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.get<PromoApiResponse>('/api/pokemon/promos');
        if (!cancelled) {
          setPromos(data.promos);
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
