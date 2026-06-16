import { useState, useEffect, useMemo } from 'react';
import { loadV1DecksData } from '../adapter';
import type { DecksV1Deck } from '../types';
import DeckGrid from '../components/DeckGrid';
import DeckFilterBar from '../components/DeckFilterBar';

export default function BrowseDecksPage() {
  const [decks, setDecks] = useState<DecksV1Deck[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('value');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadV1DecksData(controller.signal);
        setDecks(data.decks);
        setTotalValue(data.totalValue);
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError('Failed to load decks. Please try again.');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchData();
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
      result.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    }

    return result;
  }, [decks, filter, sort, search]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-spinner">Loading decks…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div className="error-message">{error}</div>
      </div>
    );
  }

  return (
    <div className="page-container">
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
