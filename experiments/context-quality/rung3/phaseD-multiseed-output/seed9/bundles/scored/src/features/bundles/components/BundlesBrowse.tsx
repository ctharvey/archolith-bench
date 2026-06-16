import { useState, useEffect, useMemo } from 'react';
import type { BundleDto } from '@/data/apiClient';
import { fetchBundles } from '@/data/bundles';
import BundleGrid from './BundleGrid';
import s from './BundlesBrowse.module.css';

type SortKey = 'discount' | 'price-asc' | 'price-desc' | 'name' | 'newest';

export default function BundlesBrowse() {
  const [bundles, setBundles] = useState<BundleDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('discount');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchBundles()
      .then((data) => {
        if (!cancelled) {
          setBundles(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, []);

  const sortedBundles = useMemo(() => {
    const list = [...bundles];
    switch (sort) {
      case 'discount':
        return list.sort((a, b) => {
          const discountA = a.originalPrice && a.price ? (a.originalPrice - a.price) / a.originalPrice : 0;
          const discountB = b.originalPrice && b.price ? (b.originalPrice - b.price) / b.originalPrice : 0;
          return discountB - discountA;
        });
      case 'price-asc':
        return list.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
      case 'price-desc':
        return list.sort((a, b) => (b.price ?? 0) - (a.price ?? 0));
      case 'name':
        return list.sort((a, b) => a.name.localeCompare(b.name));
      case 'newest':
        return list.sort((a, b) => new Date(b.createdAt ?? 0).getTime() - new Date(a.createdAt ?? 0).getTime());
      default:
        return list;
    }
  }, [bundles, sort]);

  if (loading) {
    return <div className={s.page}><div className={s.loading}>Loading bundles…</div></div>;
  }

  if (error) {
    return <div className={s.page}><div className={s.error}>{error}</div></div>;
  }

  return (
    <div className={s.page}>
      <div className={s.header}>
        <div>
          <h1 className={s.title}>Bundles</h1>
          <p className={s.subtitle}>Curated product bundles at discounted prices</p>
        </div>
        <div className={s.controls}>
          <select
            className={s.sortSelect}
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
          >
            <option value="discount">Biggest Discount</option>
            <option value="price-asc">Price: Low to High</option>
            <option value="price-desc">Price: High to Low</option>
            <option value="name">Name</option>
            <option value="newest">Newest</option>
          </select>
        </div>
      </div>
      <BundleGrid bundles={sortedBundles} />
    </div>
  );
}
