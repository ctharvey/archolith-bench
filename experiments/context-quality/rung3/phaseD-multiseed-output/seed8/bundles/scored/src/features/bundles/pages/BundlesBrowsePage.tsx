import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/data/apiClient';
import { PageHeader } from '@/ui';
import BundleCard from '../components/BundleCard';
import s from './BundlesBrowsePage.module.css';

export default function BundlesBrowsePage() {
  const { data: bundles, isLoading, error } = useQuery({
    queryKey: ['bundles'],
    queryFn: () => apiClient.getBundles(),
  });

  const sortedBundles = useMemo(() => {
    if (!bundles) return [];
    return [...bundles].sort((a, b) => {
      const discountA = a.originalPrice && a.bundlePrice
        ? (1 - a.bundlePrice / a.originalPrice) * 100
        : 0;
      const discountB = b.originalPrice && b.bundlePrice
        ? (1 - b.bundlePrice / b.originalPrice) * 100
        : 0;
      return discountB - discountA;
    });
  }, [bundles]);

  if (isLoading) {
    return (
      <div className={s.page}>
        <PageHeader title="Bundles" subtitle="Loading bundles..." />
        <div className={s.grid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={`box ${s.skeleton}`} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.page}>
        <PageHeader title="Bundles" subtitle="Failed to load bundles" />
        <p className={s.errorText}>Something went wrong. Please try again later.</p>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <PageHeader
        title="Bundles"
        subtitle={`${bundles?.length ?? 0} bundles available`}
      />
      <div className={s.grid}>
        {sortedBundles.map((bundle) => (
          <BundleCard key={bundle.bundleId} bundle={bundle} />
        ))}
      </div>
    </div>
  );
}
