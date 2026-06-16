import { useState, useEffect, useMemo } from 'react';
import type { BundleDto } from '@/data/apiClient';
import BundleGrid from '../components/BundleGrid';
import s from './BundlesBrowsePage.module.css';

type SortOption = 'discount-desc' | 'discount-asc' | 'price-asc' | 'price-desc' | 'savings-desc';

interface BundlesBrowsePageProps {
  initialBundles?: BundleDto[];
}

function sortBundles(bundles: BundleDto[], sort: SortOption): BundleDto[] {
  const sorted = [...bundles];
  switch (sort) {
    case 'discount-desc':
      sorted.sort((a, b) => {
        const aDisc = a.originalPrice > 0 ? (1 - a.currentPrice / a.originalPrice) : 0;
        const bDisc = b.originalPrice > 0 ? (1 - b.currentPrice / b.originalPrice) : 0;
        return bDisc - aDisc;
      });
      break;
    case 'discount-asc':
      sorted.sort((a, b) => {
        const aDisc = a.originalPrice > 0 ? (1 - a.currentPrice / a.originalPrice) : 0;
        const bDisc = b.originalPrice > 0 ? (1 - b.currentPrice / b.originalPrice) : 0;
        return aDisc - bDisc;
      });
      break;
    case 'price-asc':
      sorted.sort((a, b) => a.currentPrice - b.currentPrice);
      break;
    case 'price-desc':
      sorted.sort((a, b) => b.currentPrice - a.currentPrice);
      break;
    case 'savings-desc':
      sorted.sort((a, b) => (b.savings ?? 0) - (a.savings ?? 0));
      break;
  }
  return sorted;
}

export default function BundlesBrowsePage({ initialBundles }: BundlesBrowsePageProps) {
  const [bundles, setBundles] = useState<BundleDto[]>(initialBundles ?? []);
  const [isLoading, setIsLoading] = useState(!initialBundles);
  const [sort, setSort] = useState<SortOption>('discount-desc');

  useEffect(() => {
    if (initialBundles) {
      setBundles(initialBundles);
      setIsLoading(false);
      return;
    }

    // Fetch bundles from API
    const fetchBundles = async () => {
      try {
        const response = await fetch('/api/bundles');
        if (!response.ok) throw new Error('Failed to fetch bundles');
        const data: BundleDto[] = await response.json();
        setBundles(data);
      } catch (err) {
        console.error('Error fetching bundles:', err);
        setBundles([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBundles();
  }, [initialBundles]);

  const sortedBundles = useMemo(() => sortBundles(bundles, sort), [bundles, sort]);

  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>Bundle Deals</h1>
        <p className={s.subtitle}>
          Save big with curated product bundles at discounted prices
        </p>
      </div>

      <div className={s.filters}>
        <label htmlFor="sort-select" className="sr-only">Sort by</label>
        <select
          id="sort-select"
          className={s.sortSelect}
          value={sort}
          onChange={(e) => setSort(e.target.value as SortOption)}
        >
          <option value="discount-desc">Highest Discount</option>
          <option value="discount-asc">Lowest Discount</option>
          <option value="price-asc">Price: Low to High</option>
          <option value="price-desc">Price: High to Low</option>
          <option value="savings-desc">Biggest Savings</option>
        </select>
        <span className={s.count}>
          {bundles.length} bundle{bundles.length !== 1 ? 's' : ''}
        </span>
      </div>

      <BundleGrid bundles={sortedBundles} isLoading={isLoading} />
    </div>
  );
}
