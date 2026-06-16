import { useEffect, useState } from 'react';
import { loadBundlesData } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from './BundleGrid';

export default function BundlesPage() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [totalSavings, setTotalSavings] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadBundlesData(abortController.signal);
        setBundles(data.bundles);
        setTotalSavings(data.totalSavings);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message ?? 'Failed to load bundles');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className="page-loading">
        <div className="spinner" />
        <span>Loading bundles…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-error">
        <p>Something went wrong: {error}</p>
        <button onClick={() => window.location.reload()}>Try again</button>
      </div>
    );
  }

  return (
    <div className="page bundles-page">
      <BundleGrid bundles={bundles} totalSavings={totalSavings} />
    </div>
  );
}
