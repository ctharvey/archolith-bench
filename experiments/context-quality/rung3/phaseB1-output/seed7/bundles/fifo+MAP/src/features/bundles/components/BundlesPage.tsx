import { useState, useEffect } from 'react';
import { loadBundles } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from './BundleGrid';
import css from './BundlesPage.module.css';

export default function BundlesPage() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function fetchBundles() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadBundles(abortController.signal);
        setBundles(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError('Failed to load bundles. Please try again later.');
      } finally {
        setLoading(false);
      }
    }

    fetchBundles();

    return () => abortController.abort();
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
        <div className={css.error}>{error}</div>
      </div>
    );
  }

  return (
    <div className={css.page}>
      <BundleGrid bundles={bundles} />
    </div>
  );
}
