import { useState, useEffect } from 'react';
import type { DecksBrowseData } from '../types';
import { loadDecksBrowseData } from '../adapter';
import DeckCard from './DeckCard';
import css from './DecksBrowse.module.css';

export default function DecksBrowse() {
  const [data, setData] = useState<DecksBrowseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksBrowseData(abortController.signal);
        setData(result);
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError('Failed to load decks data');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    return () => abortController.abort();
  }, []);

  if (loading) {
    return <div className={css.loading}>Loading decks…</div>;
  }

  if (error) {
    return <div className={css.error}>{error}</div>;
  }

  if (!data) {
    return null;
  }

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h1 className={css.title}>Decks</h1>
        <div className={css.stats}>
          <div className={css.stat}>
            <span className={css.statLabel}>Total Decks</span>
            <span className={css.statValue}>{data.totalDecks}</span>
          </div>
          <div className={css.stat}>
            <span className={css.statLabel}>Total Value</span>
            <span className={css.statValue}>
              ${data.totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>
      </div>

      <div className={css.grid}>
        {data.decks.map(deck => (
          <DeckCard key={deck.id} deck={deck} />
        ))}
      </div>
    </div>
  );
}
