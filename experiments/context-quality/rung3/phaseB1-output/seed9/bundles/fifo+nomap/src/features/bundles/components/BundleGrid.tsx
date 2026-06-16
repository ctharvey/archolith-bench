import type { Bundle } from '../types';
import BundleCard from './BundleCard';
import css from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: Bundle[];
  totalSavings: number;
}

export default function BundleGrid({ bundles, totalSavings }: BundleGridProps) {
  if (bundles.length === 0) {
    return (
      <div className={css.empty}>
        No bundles available right now. Check back later!
      </div>
    );
  }

  return (
    <div>
      <div className={`box ${css.header}`}>
        <h2 className={css.title}>Bundles</h2>
        <span className={css.savings}>
          Save up to ${totalSavings.toFixed(2)}
        </span>
      </div>
      <div className={css.grid}>
        {bundles.map(bundle => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
