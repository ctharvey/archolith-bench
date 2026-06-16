import type { Bundle } from '../types';
import BundleCard from './BundleCard';
import css from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: Bundle[];
  loading?: boolean;
}

export default function BundleGrid({ bundles, loading }: BundleGridProps) {
  if (loading) {
    return (
      <div className={css.grid}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton-card" style={{ height: 280 }} />
        ))}
      </div>
    );
  }

  if (bundles.length === 0) {
    return (
      <div className={css.empty}>
        <p>No bundles available at the moment.</p>
      </div>
    );
  }

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Bundles</h2>
        <span className={css.count}>{bundles.length} available</span>
      </div>
      <div className={css.grid}>
        {bundles.map(bundle => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
