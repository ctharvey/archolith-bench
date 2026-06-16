import React, { useEffect, useState } from 'react';
import { fetchBundles } from './api';
import type { Bundle } from './types';
import { BundleCard } from './BundleCard';
import { PageMain, PageTitle, Grid, SkeletonRow, EmptyState } from '@/ui';

export const BundleList: React.FC = () => {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchBundles()
      .then((data) => {
        if (!cancelled) {
          setBundles(data.bundles);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <PageMain>
        <PageTitle>Bundles</PageTitle>
        <SkeletonRow count={4} />
      </PageMain>
    );
  }

  if (error) {
    return (
      <PageMain>
        <PageTitle>Bundles</PageTitle>
        <EmptyState message={error} />
      </PageMain>
    );
  }

  if (bundles.length === 0) {
    return (
      <PageMain>
        <PageTitle>Bundles</PageTitle>
        <EmptyState message="No bundles available right now." />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Bundles</PageTitle>
      <Grid columns={3} gap="md">
        {bundles.map((bundle) => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </Grid>
    </PageMain>
  );
};
