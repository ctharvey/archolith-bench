import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/data/apiClient';
import type { SealedProductPriceDto } from '@/data/apiClient';
import BundlesGrid from '../components/BundlesGrid';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['sealed-products'],
    queryFn: () => api.get<SealedProductPriceDto[]>('/api/sealed/products'),
  });

  const bundles = useMemo(() => {
    if (!data) return [];
    return data.filter(p => {
      const name = p.productName.toLowerCase();
      return (
        name.includes('bundle') ||
        name.includes('set of') ||
        name.includes('pack') ||
        name.includes('collection')
      );
    });
  }, [data]);

  if (isLoading) {
    return (
      <div className={s.page}>
        <h1 className={s.title}>Bundles</h1>
        <div className={s.loading}>Loading bundles...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.page}>
        <h1 className={s.title}>Bundles</h1>
        <div className={s.error}>Failed to load bundles. Please try again later.</div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Bundles</h1>
      <p className={s.subtitle}>
        Discover product bundles and save with discounted prices.
      </p>
      <BundlesGrid products={bundles} />
    </div>
  );
}
