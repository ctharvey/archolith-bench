import { useEffect, useState } from 'react';
import type { BundleDto } from '@/data/apiClient';
import { apiClient } from '@/data/apiClient';
import BundleGrid from '../components/BundleGrid';
import s from './BundlesBrowsePage.module.css';

export default function BundlesBrowsePage() {
  const [bundles, setBundles] = useState<BundleDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchBundles() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getBundles();
        if (!cancelled) {
          setBundles(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
        }
      } finally {
        if (!cancelled) {
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
        <div className={s.error}>{error}</div>
      </div>
    );
  }

  if (bundles.length === 0) {
    return (
      <div className={s.page}>
        <div className={s.empty}>No bundles available at this time.</div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>Bundles</h1>
      <p className={s.pageSubtitle}>Curated product bundles with discounted pricing</p>
      <BundleGrid bundles={bundles} title="Available Bundles" />
    </div>
  );
}
