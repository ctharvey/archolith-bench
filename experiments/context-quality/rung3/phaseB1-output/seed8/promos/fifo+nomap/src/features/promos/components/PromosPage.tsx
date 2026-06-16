import { useEffect, useState } from 'react';
import { loadPromosData } from '../adapter';
import type { PromoCard } from '../types';
import PromoGrid from './PromoGrid';

export default function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [totalPromos, setTotalPromos] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadPromosData(abortController.signal);
        setPromos(data.promos);
        setTotalPromos(data.totalPromos);
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    return () => abortController.abort();
  }, []);

  if (loading) {
    return <div className="loading">Loading promos…</div>;
  }

  if (error) {
    return <div className="error">Error loading promos: {error}</div>;
  }

  return <PromoGrid promos={promos} totalPromos={totalPromos} />;
}
