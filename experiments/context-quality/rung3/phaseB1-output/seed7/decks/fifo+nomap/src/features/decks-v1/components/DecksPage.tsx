import { useState, useMemo, useEffect, useCallback } from 'react';
import type { DeckV1, DecksV1Data } from '../types';
import { loadV1DecksData } from '../adapter';
import DeckGrid from './DeckGrid';
import DeckFilterBar from './DeckFilterBar';

export default function DecksPage() {
  const [data, setData] = useState<DecksV1Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('value');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    loadV1DecksData(controller.signal)
      .then(result => {
        setData(result);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message ?? 'Failed to load decks');
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  const filteredDecks = useMemo(() => {
    if (!data) return [];
    let decks = data.decks;

    // Apply format filter
    if (filter !== 'all') {
      decks = decks.filter(d => d.format.toLowerCase() === filter);
    }

    // Apply search
    if (search.trim()) {
      const q = search.toLowerCase();
      decks = decks.filter(
        d =>
          d.name.toLowerCase().includes(q) ||
          d.archetype.toLowerCase().includes(q) ||
          d.format.toLowerCase().includes(q)
      );
    }

    // Apply sort
    const sorted = [...decks];
    switch (sort) {
      case 'value':
        sorted.sort((a, b) => b.totalValue - a.totalValue);
        break;
      case 'cards':
        sorted.sort((a, b) => b.cardCount - a.cardCount);
        break;
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'updated':
        sorted.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
        break;
    }

    return sorted;
  }, [data, filter, sort, search]);

  if (loading) {
    return <div className="loading">Loading decks…</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  if (!data) {
    return <div className="error">No data available</div>;
  }

  return (
    <div className="page decks-page">
      <DeckFilterBar
        totalDecks={data.totalDecks}
        filter={filter}
        sort={sort}
        search={search}
        onFilterChange={setFilter}
        onSortChange={setSort}
        onSearchChange={setSearch}
      />
      <DeckGrid
        decks={filteredDecks}
        totalDecks={data.totalDecks}
        totalValue={data.totalValue}
        avgValue={data.avgValue}
      />
    </div>
  );
}
