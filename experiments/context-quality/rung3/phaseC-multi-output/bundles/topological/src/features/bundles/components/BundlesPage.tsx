import { useEffect, useState } from 'react';
import type { BundlesPageData } from '../types';
import { fetchBundles } from '../api';
import { BundlesGrid } from './BundlesGrid';
import { PageMain, PageTitle, SkeletonRow } from '@/ui';

export function BundlesPage() {
  const [data, setData] = useState<BundlesPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchBundles()
      .then((result) => {
        if (!cancelled) {
          setData(result);
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
        <SkeletonRow count={6} />
      </PageMain>
    );
  }

  if (error) {
    return (
      <PageMain>
        <PageTitle>Bundles</PageTitle>
        <p className="error-message">{error}</p>
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Bundles</PageTitle>
      <p className="bundles-page__subtitle">
        Save big with our curated product bundles — {data?.totalBundles ?? 0} available
      </p>
      <BundlesGrid bundles={data?.bundles ?? []} />
    </PageMain>
  );
}
