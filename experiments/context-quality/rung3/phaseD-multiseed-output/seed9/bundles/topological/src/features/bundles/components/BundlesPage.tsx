import { useEffect, useState } from 'react';
import { fetchBundles } from '../api';
import type { BundlesPageData } from '../types';
import { BundleGrid } from './BundleGrid';
import { PageMain, PageTitle, SkeletonRow } from '@/ui';

export function BundlesPage() {
  const [data, setData] = useState<BundlesPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await fetchBundles();
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
          setLoading(false);
        }
      }
    }
    load();
    return () => { cancelled = true; };
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
        <p className="error-message">{error}</p>
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Bundles</PageTitle>
      <p className="bundles-page__subtitle">
        {data?.totalBundles ?? 0} bundle{data?.totalBundles !== 1 ? 's' : ''} available
      </p>
      <BundleGrid bundles={data?.bundles ?? []} />
    </PageMain>
  );
}
