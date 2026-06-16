import { useEffect, useState } from 'react';
import { loadBundlesData } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from './BundleGrid';
import css from './BundlesPage.module.css';

export default function BundlesPage() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const { bundles: data } = await loadBundlesData(signal);
      setBundles(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError('Failed to load bundles. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className={css.page}>
        <div className={css.loading}>Loading bundles…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.page}>
        <div className={css.error}>
          <p>{error}</p>
          <button className={css.retryButton} onClick={() => fetchData()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={css.page}>
      <BundleGrid bundles={bundles} />
    </div>
  );
}
