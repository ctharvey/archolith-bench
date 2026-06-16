import { useState, useMemo, useEffect, useCallback } from 'react';
import type { DeckV1 } from '../types';
import { loadDecksV1Data } from '../adapter';
import DeckFilterBar from './DeckFilterBar';
import DeckGrid from './DeckGrid';
import s from './DecksBrowse.module.css';

export default function DecksBrowse() {
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

    loadDecksV1Data(controller.signal)
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

  const formatTotalValue = useCallback((value: number): string => {
    if (value >= 1000000) {
      return `$${(value / 1000000).toFixed(1)}M`;
    }
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}k`;
    }
    return `$${value.toFixed(2)}`;
  }, []);

  if (loading) {
    return (
      <div className={s.page}>
        <div className={s.header}>
          <h1 className={s.title}>Decks</h1>
          <p className={s.subtitle}>Loading deck data…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.page}>
        <div className={s.header}>
          <h1 className={s.title}>Decks</h1>
          <p className={s.subtitle} style={{ color: 'var(--error)' }}>
            Error: {error}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>Decks</h1>
        <p className={s.subtitle}>Browse popular decks and their market values</p>
      </div>

      <div className={s.summary}>
        <div className={s.summaryItem}>
          Total decks: <span className={s.summaryValue}>{decks.length}</span>
        </div>
        <div className={s.summaryItem}>
          Total market value: <span className={s.summaryValue}>{formatTotalValue(totalValue)}</span>
        </div>
      </div>

      <DeckFilterBar
        totalDecks={filteredDecks.length}
        filter={filter}
        sort={sort}
        search={search}
        onFilterChange={setFilter}
        onSortChange={setSort}
        onSearchChange={setSearch}
      />

      <DeckGrid decks={filteredDecks} />
    </div>
  );
}
