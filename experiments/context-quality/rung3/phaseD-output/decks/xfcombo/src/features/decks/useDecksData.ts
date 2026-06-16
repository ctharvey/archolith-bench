import { useState, useEffect } from 'react';
import { loadDecksData } from './adapter';
import type { DecksPageData } from './types';

interface UseDecksDataResult {
  data: DecksPageData | null;
  loading: boolean;
  error: string | null;
}

export function useDecksData(): UseDecksDataResult {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    let cancelled = false;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksData(abortController.signal);
        if (!cancelled) {
          setData(result);
        }
      } catch (err: any) {
        if (!cancelled && err.name !== 'AbortError') {
          setError(err.message || 'Failed to load decks');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, []);

  return { data, loading, error };
}
