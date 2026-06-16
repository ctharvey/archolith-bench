import { useEffect, useState } from 'react';
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

    async function fetch() {
      setLoading(true);
      setError(null);
      try {
        const result = await loadDecksData(abortController.signal);
        if (!abortController.signal.aborted) {
          setData(result);
        }
      } catch (err: any) {
        if (!abortController.signal.aborted) {
          setError(err?.message || 'Failed to load decks');
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetch();

    return () => abortController.abort();
  }, []);

  return { data, loading, error };
}
