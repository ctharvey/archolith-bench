import { useState, useEffect } from 'react';
import type { Bundle } from '../types';
import { loadBundlesData } from '../adapter';
import BundleCard from './BundleCard';
import css from './BundleGrid.module.css';

export default function BundleGrid() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    loadBundlesData(abortController.signal)
      .then(({ bundles }) => {
        setBundles(bundles);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load bundles');
          setLoading(false);
        }
      });
    return () => abortController.abort();
  }, []);

  if (loading) {
    return <div className={css.grid}>Loading bundles...</div>;
  }

  if (error) {
    return <div className={css.grid}>Error: {error}</div>;
  }

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Bundles</h2>
        <span className={css.count}>{bundles.length} available</span>
      </div>
      <div className={css.grid}>
        {bundles.map((bundle) => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
