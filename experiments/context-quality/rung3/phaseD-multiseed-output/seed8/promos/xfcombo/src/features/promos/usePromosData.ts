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

interface PromosDataResult {
  promos: PromoSet[];
  loading: boolean;
  error: string | null;
}

export function usePromosData(): PromosDataResult {
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
          const mapped: PromoSet[] = (data.sets || []).map((s: any) => ({
            id: s.core?.id || s.id,
            name: s.core?.name || s.name,
            code: s.core?.code || s.code || '',
            serie: s.serie?.serieName || s.serieName || '',
            releaseYear: s.core?.releaseDate
              ? new Date(s.core.releaseDate).getFullYear()
              : s.releaseDate
                ? new Date(s.releaseDate).getFullYear()
                : 0,
            cardCount: s.core?.totalCards || s.totalCards || 0,
            logoUrl: s.core?.logoUrl || s.logoUrl || null,
            symbolUrl: s.core?.symbolUrl || s.symbolUrl || null,
          }));

          setPromos(mapped);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || 'An error occurred while fetching promo data');
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
