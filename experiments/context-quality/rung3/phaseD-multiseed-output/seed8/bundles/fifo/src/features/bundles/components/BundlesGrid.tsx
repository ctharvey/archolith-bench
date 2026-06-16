import { useState, useEffect, useMemo } from 'react';
import type { Bundle } from '../types';
import { loadBundlesData } from '../adapter';
import BundleCard from './BundleCard';
import css from './BundlesGrid.module.css';

interface BundlesGridProps {
  onBundleClick?: (bundle: Bundle) => void;
}

export default function BundlesGrid({ onBundleClick }: BundlesGridProps) {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'discount' | 'price' | 'name'>('discount');

  useEffect(() => {
    const controller = new AbortController();
    
    async function fetchBundles() {
      try {
        setLoading(true);
        const data = await loadBundlesData(controller.signal);
        setBundles(data.bundles);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load bundles');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchBundles();
    return () => controller.abort();
  }, []);

  const sortedBundles = useMemo(() => {
    const active = bundles.filter(b => b.active);
    const inactive = bundles.filter(b => !b.active);
    
    const sortFn = (a: Bundle, b: Bundle) => {
      switch (sortBy) {
        case 'discount':
          return b.discountPercent - a.discountPercent;
        case 'price':
          return a.discountedPrice - b.discountedPrice;
        case 'name':
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    };

    return [...active.sort(sortFn), ...inactive.sort(sortFn)];
  }, [bundles, sortBy]);

  const averageDiscount = bundles.length > 0
    ? Math.round(bundles.reduce((sum, b) => sum + b.discountPercent, 0) / bundles.length)
    : 0;

  if (loading) {
    return (
      <div className={css.container}>
        <div className={css.loading}>Loading bundles...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.container}>
        <div className={css.empty}>Error: {error}</div>
      </div>
    );
  }

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h2 className={css.title}>Bundles</h2>
        <div className={css.stats}>
          <span>
            <span className={css.statValue}>{bundles.length}</span> bundles
          </span>
          <span>
            Avg <span className={css.statValue}>{averageDiscount}%</span> off
          </span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="sets-sort-select"
          >
            <option value="discount">Sort: Best Discount</option>
            <option value="price">Sort: Lowest Price</option>
            <option value="name">Sort: Name</option>
          </select>
        </div>
      </div>

      {sortedBundles.length === 0 ? (
        <div className={css.empty}>No bundles available at this time.</div>
      ) : (
        <div className={css.grid}>
          {sortedBundles.map((bundle) => (
            <BundleCard
              key={bundle.id}
              bundle={bundle}
              onClick={onBundleClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}
