import type { Bundle } from '../types';
import { BundleCard } from './BundleCard';
import { Grid, EmptyState } from '@/ui';

interface BundlesGridProps {
  bundles: Bundle[];
}

export function BundlesGrid({ bundles }: BundlesGridProps) {
  if (bundles.length === 0) {
    return (
      <EmptyState
        title="No bundles available"
        description="Check back later for new product bundles."
      />
    );
  }

  return (
    <Grid columns={3} gap="lg">
      {bundles.map((bundle) => (
        <BundleCard key={bundle.id} bundle={bundle} />
      ))}
    </Grid>
  );
}
