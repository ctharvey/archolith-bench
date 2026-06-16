import { useEffect, useState } from 'react';
import type { BundleDto } from '@/data/apiClient';
import { apiClient } from '@/data/apiClient';
import BundleCard from '../components/BundleCard';
import s from './BundlesBrowsePage.module.css';

export default function BundlesBrowsePage() {
  const [bundles, setBundles] = useState<BundleDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchBundles() {
      try {
        const data = await apiClient.getBundles();
        if (!cancelled) {
          setBundles(data);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
          setLoading(false);
        }
      }
    }
    fetchBundles();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className={s.page}>
        <div className={s.loading}>Loading bundles...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.page}>
        <div className={s.empty}>{error}</div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>Bundles</h1>
        <p className={s.subtitle}>Save with curated product bundles</p>
      </div>
      {bundles.length === 0 ? (
        <div className={s.empty}>No bundles available right now.</div>
      ) : (
        <div className={s.grid}>
          {bundles.map((bundle) => (
            <BundleCard key={bundle.id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  );
}
