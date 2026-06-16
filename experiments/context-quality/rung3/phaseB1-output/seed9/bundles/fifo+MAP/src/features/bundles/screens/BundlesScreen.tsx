import { useEffect, useState } from 'react';
import { loadBundles } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from '../components/BundleGrid';
import css from './BundlesScreen.module.css';

export default function BundlesScreen() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBundles = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loadBundles(signal);
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
    fetchBundles(controller.signal);
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <div className={css.screen}>
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
    <div className={css.screen}>
      <BundleGrid bundles={bundles} loading={loading} />
    </div>
  );
}
