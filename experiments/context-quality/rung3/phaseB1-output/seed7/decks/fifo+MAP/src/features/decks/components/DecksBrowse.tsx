import { useState, useEffect, useMemo } from 'react';
import type { Deck, DecksBrowseData } from '../types';
import { loadDecksBrowseData } from '../adapter';
import DeckCard from './DeckCard';
import css from './DecksBrowse.module.css';

export default function DecksBrowse() {
  const [data, setData] = useState<DecksBrowseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('value');

  useEffect(() => {
    const controller = new AbortController();
    
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksBrowseData(controller.signal);
        setData(result);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return;
        setError('Failed to load decks. Please try again.');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    return () => controller.abort();
  }, []);

  const filteredAndSorted = useMemo(() => {
    if (!data) return [];

    let decks = [...data.decks];

    // Filter by search
    if (search.trim()) {
      const query = search.toLowerCase();
      decks = decks.filter(
        d =>
          d.name.toLowerCase().includes(query) ||
          d.format.toLowerCase().includes(query)
      );
    }

    // Sort
    switch (sort) {
      case 'value':
        decks.sort((a, b) => b.totalValue - a.totalValue);
        break;
      case 'name':
        decks.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'cards':
        decks.sort((a, b) => b.cardCount - a.cardCount);
        break;
      case 'updated':
        decks.sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime());
        break;
      default:
        break;
    }

    return decks;
  }, [data, search, sort]);

  if (loading) {
    return <div className={css.container}><div className={css.loading}>Loading decks...</div></div>;
  }

  if (error) {
    return <div className={css.container}><div className={css.error}>{error}</div></div>;
  }

  if (!data) {
    return <div className={css.container}><div className={css.empty}>No data available</div></div>;
  }

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h1 className={css.title}>Decks</h1>
        <p className={css.subtitle}>Browse and compare deck market values</p>
      </div>

      <div className={css.statsBar}>
        <div className={css.statItem}>
          <span className={css.statLabel}>Total Decks</span>
          <span className={css.statValue}>{data.totalDecks}</span>
        </div>
        <div className={css.statItem}>
          <span className={css.statLabel}>Total Market Value</span>
          <span className={`${css.statValue} ${css.statValueAccent}`}>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            }).format(data.totalValue)}
          </span>
        </div>
        <div className={css.statItem}>
          <span className={css.statLabel}>Avg Deck Value</span>
          <span className={css.statValue}>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            }).format(data.totalValue / data.totalDecks)}
          </span>
        </div>
      </div>

      <div className={css.controls}>
        <input
          type="text"
          placeholder="Search decks by name or format..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={css.searchInput}
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className={css.sortSelect}
        >
          <option value="value">Sort by: Total Value</option>
          <option value="name">Sort by: Name</option>
          <option value="cards">Sort by: Card Count</option>
          <option value="updated">Sort by: Last Updated</option>
        </select>
      </div>

      <div className={css.grid}>
        {filteredAndSorted.length === 0 ? (
          <div className={css.empty}>No decks match your search</div>
        ) : (
          filteredAndSorted.map((deck) => (
            <DeckCard key={deck.id} deck={deck} />
          ))
        )}
      </div>
    </div>
  );
}
