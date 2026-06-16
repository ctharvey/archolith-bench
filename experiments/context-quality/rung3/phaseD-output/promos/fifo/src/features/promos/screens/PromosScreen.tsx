import { useEffect, useState } from 'react';
import { loadPromos } from '../adapter';
import type { PromoCard } from '../types';
import PromoGrid from '../components/PromoGrid';

export default function PromosScreen() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    async function fetch() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadPromos(abortController.signal);
        setPromos(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError('Failed to load promo cards.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    
    fetch();
    
    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className="page" style={{ padding: 20 }}>
        <div className="loading">Loading promos…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page" style={{ padding: 20 }}>
        <div className="error">{error}</div>
      </div>
    );
  }

  return (
    <div className="page">
      <PromoGrid promos={promos} />
    </div>
  );
}
