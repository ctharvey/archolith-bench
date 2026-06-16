import { useState, useEffect } from 'react';
import { loadBundles } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from '../components/BundleGrid';
import css from './BundlesPage.module.css';

export default function BundlesPage() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBundles = async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setError(null);
      const data = await loadBundles(signal);
      setBundles(data);
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Failed to load bundles');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchBundles(controller.signal);
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <div className={css.page}>
        <div className={css.error}>
          <p>{error}</p>
          <button className={css.retryButton} onClick={() => fetchBundles()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={css.page}>
      <h1 className={css.pageTitle}>Bundle Deals</h1>
      <p className={css.pageSubtitle}>Save big with our curated product bundles</p>
      <BundleGrid bundles={bundles} loading={loading} />
    </div>
  );
}
