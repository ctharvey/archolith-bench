import { useState, useEffect, useMemo } from 'react';
import { loadDecksData } from '../adapter';
import type { Deck } from '../types';
import DeckGrid from '../components/DeckGrid';
import DeckFilterBar from '../components/DeckFilterBar';

export default function DecksBrowsePage() {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('value');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    loadDecksData(controller.signal)
      .then(data => {
        setDecks(data.decks);
        setTotalValue(data.totalValue);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const filteredDecks = useMemo(() => {
    let result = [...decks];

    // Apply filter
    if (filter === 'standard') {
      result = result.filter(d => d.format === 'Standard');
    } else if (filter === 'expanded') {
      result = result.filter(d => d.format === 'Expanded');
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
      result.sort((a, b) => b.totalValueNum - a.totalValueNum);
    } else if (sort === 'winrate') {
      result.sort((a, b) => b.winRateNum - a.winRateNum);
    } else if (sort === 'popularity') {
      result.sort((a, b) => b.popularityNum - a.popularityNum);
    } else if (sort === 'cards') {
      result.sort((a, b) => b.cardCount - a.cardCount);
    } else if (sort === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name));
    }

    return result;
  }, [decks, filter, sort, search]);

  if (loading) {
    return <div className="page-loading">Loading decks…</div>;
  }

  if (error) {
    return <div className="page-error">Error: {error}</div>;
  }

  return (
    <div className="page decks-browse-page">
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
