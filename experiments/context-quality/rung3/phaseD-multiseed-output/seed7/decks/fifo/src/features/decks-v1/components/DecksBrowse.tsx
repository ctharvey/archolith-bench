import { useState, useEffect, useMemo } from 'react';
import type { DeckV1, DecksV1Data } from '../types';
import { loadDecksV1Data } from '../adapter';
import DeckCard from './DeckCard';
import css from './DecksBrowse.module.css';

export default function DecksBrowse() {
  const [data, setData] = useState<DecksV1Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksV1Data(abortController.signal);
        if (!abortController.signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!abortController.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load decks');
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchData();
    return () => abortController.abort();
  }, []);

  const totalValueFormatted = useMemo(() => {
    if (!data) return '$0';
    if (data.totalValue >= 1000) {
      return `$${(data.totalValue / 1000).toFixed(1)}k`;
    }
    return `$${data.totalValue.toFixed(2)}`;
  }, [data]);

  if (loading) {
    return (
      <div className={css.container}>
        <div className={css.loading}>Loading decks…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={css.container}>
        <div className={css.error}>{error}</div>
      </div>
    );
  }

  if (!data || data.decks.length === 0) {
    return (
      <div className={css.container}>
        <div className={css.empty}>No decks found</div>
      </div>
    );
  }

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h1 className={css.title}>Decks</h1>
        <div className={css.totalValue}>
          Total value: <strong>{totalValueFormatted}</strong>
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
