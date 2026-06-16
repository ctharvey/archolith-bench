import { useState, useMemo, useEffect, useCallback } from 'react';
import type { DeckV1 } from '../types';
import { loadV1DecksData } from '../adapter';
import DeckGrid from './DeckGrid';
import DeckFilterBar from './DeckFilterBar';

export default function DecksBrowseScreen() {
  const [decks, setDecks] = useState<DeckV1[]>([]);
  const [totalValue, setTotalValue] = useState(0);
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
      .then(data => {
        setDecks(data.decks);
        setTotalValue(data.totalValue);
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
    let result = [...decks];

    // Apply format filter
    if (filter !== 'all') {
      result = result.filter(d => d.format.toLowerCase() === filter);
    }

    // Apply search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        d =>
          d.name.toLowerCase().includes(q) ||
          d.archetype.toLowerCase().includes(q) ||
          d.format.toLowerCase().includes(q)
      );
    }

    // Apply sort
    if (sort === 'value') {
      result.sort((a, b) => b.totalValue - a.totalValue);
    } else if (sort === 'cards') {
      result.sort((a, b) => b.cardCount - a.cardCount);
    } else if (sort === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sort === 'updated') {
      result.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    }

    return result;
  }, [decks, filter, sort, search]);

  if (loading) {
    return <div className="loading">Loading decks…</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="decks-browse-screen">
      <DeckFilterBar
        totalDecks={decks.length}
        filter={filter}
        sort={sort}
        search={search}
        onFilterChange={setFilter}
        onSortChange={setSort}
        onSearchChange={setSearch}
      />
      <DeckGrid decks={filteredDecks} totalValue={totalValue} />
    </div>
  );
}
