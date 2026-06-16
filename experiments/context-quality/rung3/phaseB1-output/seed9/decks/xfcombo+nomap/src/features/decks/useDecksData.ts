import { useEffect, useState } from 'react';
import { api } from '@/data/apiClient';
import type { DecksPageData } from './types';
import { loadDecksData } from './adapter';

export function useDecksData() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksData(abortController.signal);
        setData(result);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load decks');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    return () => abortController.abort();
  }, []);

  return { data, loading, error };
}
