import { useState, useEffect } from 'react';

interface PromoData {
  id: string;
  name: string;
  code: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
}

interface UsePromosDataResult {
  promos: PromoData[];
  loading: boolean;
  error: string | null;
}

export function usePromosData(): UsePromosDataResult {
  const [promos, setPromos] = useState<PromoData[]>([]);
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
          throw new Error(`Failed to fetch promos: ${response.statusText}`);
        }
        const data: PromoData[] = await response.json();
        if (!cancelled) {
          setPromos(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
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
