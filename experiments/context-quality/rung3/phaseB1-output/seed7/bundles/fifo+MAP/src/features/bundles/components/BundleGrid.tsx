import type { Bundle } from '../types';
import BundleCard from './BundleCard';
import css from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: Bundle[];
}

export default function BundleGrid({ bundles }: BundleGridProps) {
  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Bundles</h2>
        <span className={css.count}>{bundles.length} available</span>
      </div>
      {bundles.length === 0 ? (
        <div className={css.empty}>No bundles available right now.</div>
      ) : (
        <div className={css.grid}>
          {bundles.map(bundle => (
            <BundleCard key={bundle.id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  );
}
