import { useEffect, useState } from 'react';
import type { PromoCard } from '../types';
import { loadPromos } from '../adapter';
import PromosGrid from './PromosGrid';
import css from './PromosPage.module.css';

export default function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    loadPromos(abortController.signal)
      .then(data => {
        setPromos(data);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load promos');
          setLoading(false);
        }
      });

    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className={css.page}>
        <div className={css.loading}>Loading promos…</div>
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
      <PromosGrid promos={promos} />
    </div>
  );
}
