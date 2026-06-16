import { useEffect, useState } from 'react';
import { loadPromos } from '../adapter';
import type { PromoCard } from '../types';
import PromoGrid from './PromoGrid';

export default function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    async function fetchPromos() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadPromos(abortController.signal);
        setPromos(data);
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchPromos();
    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--t-4)' }}>
        Loading promo cards…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--error)' }}>
        Error loading promos: {error}
      </div>
    );
  }

  return (
    <div className="page-container">
      <PromoGrid promos={promos} />
    </div>
  );
}
