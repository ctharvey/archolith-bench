import { useState, useEffect } from 'react';

interface PromoSet {
  id: string;
  name: string;
  code: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
}

interface UsePromosDataResult {
  promos: PromoSet[];
  loading: boolean;
  error: string | null;
}

export function usePromosData(): UsePromosDataResult {
  const [promos, setPromos] = useState<PromoSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPromos() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch('/api/pokemon/sets?type=promo');
        if (!response.ok) {
          throw new Error(`Failed to fetch promo sets: ${response.statusText}`);
        }
        const data = await response.json();
        if (!cancelled) {
          const mapped: PromoSet[] = data.map((item: any) => ({
            id: item.core?.id || item.id,
            name: item.core?.name || item.name,
            code: item.core?.code || item.code || '',
            releaseYear: item.core?.releaseDate
              ? new Date(item.core.releaseDate).getFullYear()
              : item.releaseYear || 0,
            cardCount: item.core?.totalCards || item.totalCards || 0,
            logoUrl: item.core?.logoUrl || item.logoUrl || null,
          }));
          setPromos(mapped);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || 'An error occurred');
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
