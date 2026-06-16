import { useState, useEffect } from 'react';
import type { Bundle } from '../types';
import { loadBundles } from '../adapter';
import BundleCard from './BundleCard';
import css from './BundleGrid.module.css';

export default function BundleGrid() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    async function fetch() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadBundles(abortController.signal);
        setBundles(data);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message ?? 'Failed to load bundles');
        }
      } finally {
        setLoading(false);
      }
    }

    fetch();
    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className={css.empty}>
        Loading bundles…
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.empty}>
        Error: {error}
      </div>
    );
  }

  const activeBundles = bundles.filter(b => b.active);

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Bundles</h2>
        <span className={css.count}>{activeBundles.length} available</span>
      </div>
      {activeBundles.length === 0 ? (
        <div className={css.empty}>No bundles available right now.</div>
      ) : (
        <div className={css.grid}>
          {activeBundles.map(bundle => (
            <BundleCard key={bundle.id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  );
}
