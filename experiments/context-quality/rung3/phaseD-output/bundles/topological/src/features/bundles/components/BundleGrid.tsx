import type { Bundle } from '../types';
import { BundleCard } from './BundleCard';
import { Grid, EmptyState } from '@/ui';

interface BundleGridProps {
  bundles: Bundle[];
}

export function BundleGrid({ bundles }: BundleGridProps) {
  if (bundles.length === 0) {
    return <EmptyState message="No bundles available at this time." />;
  }

  return (
    <Grid className="bundle-grid">
      {bundles.map((bundle) => (
        <BundleCard key={bundle.id} bundle={bundle} />
      ))}
    </Grid>
  );
}
