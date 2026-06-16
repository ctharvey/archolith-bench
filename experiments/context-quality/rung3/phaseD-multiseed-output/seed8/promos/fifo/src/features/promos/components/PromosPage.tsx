import { useEffect, useState } from 'react';
import { loadPromosData } from '../adapter';
import type { PromoCard } from '../types';
import PromoGrid from './PromoGrid';

export default function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    
    loadPromosData(controller.signal)
      .then(data => {
        setPromos(data.promos);
        setYears(data.years);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load promos');
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="page-loading">
        <p>Loading promos…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-error">
        <p>Error: {error}</p>
      </div>
    );
  }

  return <PromoGrid promos={promos} years={years} />;
}
