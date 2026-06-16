import { useEffect, useState } from 'react';
import type { PromoCard } from '../types';
import { loadPromos } from '../adapter';
import PromoList from './PromoList';
import css from './PromosScreen.module.css';

export default function PromosScreen() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loadPromos(signal);
      setPromos(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError('Failed to load promo cards. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const abortController = new AbortController();
    fetchData(abortController.signal);
    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className={css.screen}>
        <div className={css.loading}>Loading promos…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.screen}>
        <div className={css.error}>
          <span>{error}</span>
          <button className={css.retryButton} onClick={() => fetchData()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={css.screen}>
      <PromoList promos={promos} />
    </div>
  );
}
