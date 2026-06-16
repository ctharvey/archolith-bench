import { useEffect, useState } from 'react';
import { loadPromos } from '../adapter';
import type { PromoCard } from '../types';
import PromoGrid from './PromoGrid';

export default function PromosPage() {
  const [cards, setCards] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadPromos(abortController.signal);
        setCards(data);
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
    return <div className="loading">Loading promo cards…</div>;
  }

  if (error) {
    return <div className="error">Failed to load promo cards: {error}</div>;
  }

  return <PromoGrid cards={cards} />;
}
