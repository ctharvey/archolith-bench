import type { Bundle } from '../types';
import BundleCard from './BundleCard';

interface BundleGridProps {
  bundles: Bundle[];
}

export default function BundleGrid({ bundles }: BundleGridProps) {
  if (bundles.length === 0) {
    return (
      <div className="bundle-empty">
        <p>No bundles available at this time.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="bundle-header">
        <h2 className="bundle-title">Bundles</h2>
        <span className="bundle-count">{bundles.length} available</span>
      </div>
      <div className="bundle-grid">
        {bundles.map(bundle => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
