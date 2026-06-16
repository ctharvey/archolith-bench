import { useState, useEffect } from 'react';

interface PromoSet {
  id: string;
  name: string;
  code: string;
  serie: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
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
        const res = await fetch('/api/pokemon/sets?type=promo');
        if (!res.ok) throw new Error(`Failed to fetch promos: ${res.statusText}`);
        const data: PromoSet[] = await res.json();
        if (!cancelled) setPromos(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchPromos();
    return () => { cancelled = true; };
  }, []);

  return { promos, loading, error };
}
