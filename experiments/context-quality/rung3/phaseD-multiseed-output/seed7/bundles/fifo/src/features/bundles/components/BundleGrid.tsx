import type { Bundle } from '../types';
import BundleCard from './BundleCard';
import styles from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: Bundle[];
}

export default function BundleGrid({ bundles }: BundleGridProps) {
  if (bundles.length === 0) {
    return (
      <div className="empty-state">
        <p>No bundles available at the moment.</p>
      </div>
    );
  }

  return (
    <div>
      <div className={`box ${styles.header}`}>
        <h2 className={styles.title}>Bundles</h2>
        <span className={styles.count}>{bundles.length} available</span>
      </div>
      <div className={styles.grid}>
        {bundles.map(bundle => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
