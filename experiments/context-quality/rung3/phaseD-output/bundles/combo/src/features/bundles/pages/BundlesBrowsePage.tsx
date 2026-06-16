import { useEffect, useState } from 'react';
import BundleGrid from '../components/BundleGrid';
import s from './BundlesBrowsePage.module.css';

interface BundleApiItem {
  bundleName: string;
  bundlePrice: number;
  originalTotal: number;
  products: Array<{
    productName: string;
    marketPrice: number | null;
    imageUrl?: string | null;
  }>;
  imageUrl?: string | null;
}

export default function BundlesBrowsePage() {
  const [bundles, setBundles] = useState<BundleApiItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchBundles() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch('/api/bundles');
        if (!res.ok) throw new Error(`Failed to load bundles (${res.status})`);
        const data: BundleApiItem[] = await res.json();
        if (!cancelled) setBundles(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchBundles();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className={s.page}>
        <div className={s.loading}>Loading bundles…</div>
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
        <div className={s.empty}>
          <div className={s.emptyIcon}>📦</div>
          <span>No bundles available right now.</span>
        </div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>Bundles</h1>
      <p className={s.pageSubtitle}>Save money with curated product bundles</p>
      <BundleGrid bundles={bundles} title="Available Bundles" />
    </div>
  );
}
