import { useEffect, useState } from 'react';
import { loadDecksData } from './adapter';
import type { DecksPageData } from './types';

export function useDecksData() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    setLoading(true);
    setError(null);

    loadDecksData(abortController.signal)
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((err: any) => {
        if (err.name !== 'AbortError') {
          setError(err.message ?? 'Failed to load decks');
          setLoading(false);
        }
      });

    return () => abortController.abort();
  }, []);

  return { data, loading, error };
}
