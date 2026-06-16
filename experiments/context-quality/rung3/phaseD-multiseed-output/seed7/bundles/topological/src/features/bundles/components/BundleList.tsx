import { useBundles } from '../hooks';
import { BundleCard } from './BundleCard';
import { SkeletonRow, EmptyState, Grid } from '@/ui';

export function BundleList() {
  const { data: bundles, isLoading, isError, error } = useBundles();

  if (isLoading) {
    return (
      <Grid cols={3} gap="md">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonRow key={i} rows={4} />
        ))}
      </Grid>
    );
  }

  if (isError) {
    return (
      <EmptyState
        title="Failed to load bundles"
        message={error?.message ?? 'An unexpected error occurred.'}
      />
    );
  }

  if (!bundles || bundles.length === 0) {
    return (
      <EmptyState
        title="No bundles available"
        message="Check back later for new product bundles."
      />
    );
  }

  return (
    <Grid cols={3} gap="md">
      {bundles.map((bundle) => (
        <BundleCard key={bundle.id} bundle={bundle} />
      ))}
    </Grid>
  );
}
