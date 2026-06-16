import { useState, useMemo, useEffect, useCallback } from 'react';
import type { Bundle } from '../types';
import { loadBundles } from '../adapter';
import BundleCard from './BundleCard';
import css from './BundlesBrowse.module.css';

type SortKey = 'discount' | 'price' | 'name' | 'expiry';
type FilterKey = 'all' | 'active' | 'expiring';

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'discount', label: 'Biggest discount' },
  { value: 'price', label: 'Price: low to high' },
  { value: 'name', label: 'Name' },
  { value: 'expiry', label: 'Expiring soon' },
];

export default function BundlesBrowse() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('discount');
  const [filter, setFilter] = useState<FilterKey>('all');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    loadBundles(controller.signal)
      .then(data => {
        setBundles(data);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message ?? 'Failed to load bundles');
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  const filtered = useMemo(() => {
    let result = [...bundles];

    // Filter
    if (filter === 'active') {
      result = result.filter(b => b.active);
    } else if (filter === 'expiring') {
      const now = new Date();
      const sevenDays = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      result = result.filter(b => b.expiresAt && new Date(b.expiresAt) <= sevenDays && new Date(b.expiresAt) > now);
    }

    // Search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(b =>
        b.name.toLowerCase().includes(q) ||
        b.description.toLowerCase().includes(q) ||
        b.items.some(item => item.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      switch (sort) {
        case 'discount':
          return b.discountPercent - a.discountPercent;
        case 'price':
          return a.discountedPrice - b.discountedPrice;
        case 'name':
          return a.name.localeCompare(b.name);
        case 'expiry': {
          if (!a.expiresAt && !b.expiresAt) return 0;
          if (!a.expiresAt) return 1;
          if (!b.expiresAt) return -1;
          return new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime();
        }
        default:
          return 0;
      }
    });

    return result;
  }, [bundles, filter, search, sort]);

  const activeCount = useMemo(() => bundles.filter(b => b.active).length, [bundles]);
  const expiringCount = useMemo(() => {
    const now = new Date();
    const sevenDays = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    return bundles.filter(b => b.expiresAt && new Date(b.expiresAt) <= sevenDays && new Date(b.expiresAt) > now).length;
  }, [bundles]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
  }, []);

  const handleSortChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSort(e.target.value as SortKey);
  }, []);

  if (loading) {
    return (
      <div className={css.page}>
        <div className={css.loading}>Loading bundles…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.page}>
        <div className={css.empty}>Error: {error}</div>
      </div>
    );
  }

  return (
    <div className={css.page}>
      <div className={css.header}>
        <h1 className={css.title}>Bundles</h1>
        <p className={css.subtitle}>
          Save big with curated product bundles
        </p>
      </div>

      <div className={css.controls}>
        <div className={css.filterGroup}>
          <button
            className={`${css.filterPill} ${filter === 'all' ? css.filterPillActive : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({bundles.length})
          </button>
          <button
            className={`${css.filterPill} ${filter === 'active' ? css.filterPillActive : ''}`}
            onClick={() => setFilter('active')}
          >
            Active ({activeCount})
          </button>
          <button
            className={`${css.filterPill} ${filter === 'expiring' ? css.filterPillActive : ''}`}
            onClick={() => setFilter('expiring')}
          >
            Expiring soon ({expiringCount})
          </button>
        </div>

        <input
          className={css.searchInput}
          type="text"
          placeholder="Search bundles, items…"
          value={search}
          onChange={handleSearchChange}
        />

        <select
          className={css.sortSelect}
          value={sort}
          onChange={handleSortChange}
        >
          {SORT_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className={css.empty}>
          {search ? 'No bundles match your search.' : 'No bundles available.'}
        </div>
      ) : (
        <div className={css.grid}>
          {filtered.map(bundle => (
            <BundleCard key={bundle.id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  );
}
