import { useState, useEffect } from 'react';
import { loadBundles } from '../adapter';
import type { Bundle } from '../types';
import BundleGrid from './BundleGrid';

export default function BundleScreen() {
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
        if (err instanceof Error && err.name !== 'AbortError') {
          setError('Failed to load bundles. Please try again later.');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchBundles();

    return () => abortController.abort();
  }, []);

  if (loading) {
    return (
      <div className="bundle-screen">
        <div className="bundle-loading">Loading bundles...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bundle-screen">
        <div className="bundle-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="bundle-screen">
      <BundleGrid bundles={bundles} />
    </div>
  );
}
