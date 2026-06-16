import { useEffect, useState } from 'react';
import { loadPromosData } from './adapter';
import type { PromoCard } from './types';
import PromosGrid from './components/PromosGrid';

export default function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadPromosData(controller.signal)
      .then(data => {
        setPromos(data);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  if (loading) return <div>Loading promos...</div>;
  if (error) return <div>Error: {error}</div>;

  return <PromosGrid promos={promos} />;
}
