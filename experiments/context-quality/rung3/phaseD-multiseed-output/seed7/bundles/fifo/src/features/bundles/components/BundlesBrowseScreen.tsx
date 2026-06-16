import { useState, useMemo, useEffect } from 'react';
import type { Bundle } from '../types';
import { loadBundles } from '../adapter';
import BundleGrid from './BundleGrid';
import BundleFilterBar from './BundleFilterBar';

export default function BundlesBrowseScreen() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('discount');
  const [search, setSearch] = useState('');

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

  const filteredAndSorted = useMemo(() => {
    let result = [...bundles];

    // Filter
    if (filter === 'active') {
      result = result.filter(b => b.active);
    }

    // Search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        b =>
          b.name.toLowerCase().includes(q) ||
          b.description.toLowerCase().includes(q)
      );
    }

    // Sort
    if (sort === 'discount') {
      result.sort((a, b) => b.discountPercent - a.discountPercent);
    } else if (sort === 'price') {
      result.sort((a, b) => a.discountedPrice - b.discountedPrice);
    } else if (sort === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sort === 'items') {
      result.sort((a, b) => b.items.length - a.items.length);
    }

    return result;
  }, [bundles, filter, sort, search]);

  const activeCount = bundles.filter(b => b.active).length;

  if (loading) {
    return <div className="loading-spinner">Loading bundles…</div>;
  }

  if (error) {
    return <div className="error-message">Error: {error}</div>;
  }

  return (
    <div className="browse-screen">
      <BundleFilterBar
        totalBundles={bundles.length}
        activeCount={activeCount}
        filter={filter}
        sort={sort}
        search={search}
        onFilterChange={setFilter}
        onSortChange={setSort}
        onSearchChange={setSearch}
      />
      <BundleGrid bundles={filteredAndSorted} />
    </div>
  );
}
