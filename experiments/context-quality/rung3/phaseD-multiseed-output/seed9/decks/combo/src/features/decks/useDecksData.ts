import { useEffect, useState } from 'react';
import { loadDecksData } from './adapter';
import type { DecksPageData } from './types';

export function useDecksData() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    setLoading(true);
    setError(null);

    loadDecksData(abort.signal)
      .then(setData)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load decks');
        }
      })
      .finally(() => setLoading(false));

    return () => abort.abort();
  }, []);

  return { data, loading, error };
}
