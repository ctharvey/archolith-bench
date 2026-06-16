import { useEffect, useState } from 'react';
import { api } from '@/data/apiClient';
import type { DeckBrowseDto } from '@/data/apiClient';
import type { DecksPageData } from './types';

export function useDecksData(): {
  data: DecksPageData | null;
  loading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const result = await api.getDecks({}, abortController.signal);
        if (cancelled) return;

        const decks = result.data.map((d: DeckBrowseDto) => ({
          id: d.id,
          name: d.name,
          format: d.format,
          totalValue: d.totalValue,
          cardCount: d.cardCount,
          updatedAt: d.updatedAt,
        }));

        const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);

        setData({
          decks,
          totalValue,
          totalDecks: decks.length,
        });
      } catch (err: any) {
        if (cancelled) return;
        setError(err?.message || 'Failed to load decks');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, []);

  return { data, loading, error };
}
