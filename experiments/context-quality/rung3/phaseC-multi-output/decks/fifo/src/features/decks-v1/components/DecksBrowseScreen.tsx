import { useState, useEffect, useCallback } from 'react';
import { loadDecksV1Data } from '../adapter';
import type { DeckV1 } from '../types';
import DeckFilterBar from './DeckFilterBar';
import DeckGrid from './DeckGrid';

export default function DecksBrowseScreen() {
  const [decks, setDecks] = useState<DeckV1[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('updated');

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loadDecksV1Data(signal);
      setDecks(data.decks);
      setTotalValue(data.totalValue);
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message ?? 'Failed to load decks');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="page">
        <div className="page-content">
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--t-4)' }}>
            Loading decks…
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-content">
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--danger)' }}>
            {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-content">
        <DeckFilterBar
          totalDecks={decks.length}
          search={search}
          sort={sort}
          onSearchChange={setSearch}
          onSortChange={setSort}
        />
        <DeckGrid
          decks={decks}
          totalValue={totalValue}
          search={search}
          sort={sort}
        />
      </div>
    </div>
  );
}
