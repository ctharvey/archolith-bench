import { useState, useEffect } from 'react';
import type { PromoCard } from '../types';
import { loadPromosData } from '../adapter';
import PromoGrid from './PromoGrid';
import css from './PromosPage.module.css';

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
        const data = await loadPromosData(abortController.signal);
        if (!abortController.signal.aborted) {
          setCards(data);
        }
      } catch (err) {
        if (!abortController.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load promo cards');
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className={css.page}>
        <div className={css.loading}>Loading promo cards…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.page}>
        <div className={css.error}>{error}</div>
      </div>
    );
  }

  return (
    <div className={css.page}>
      <PromoGrid cards={cards} />
    </div>
  );
}
