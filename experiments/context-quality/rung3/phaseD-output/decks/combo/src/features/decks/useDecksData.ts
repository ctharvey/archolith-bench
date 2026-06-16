import { useEffect, useState } from 'react';
import { loadDecksData } from './adapter';
import type { DecksPageData } from './types';

export function useDecksData() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    let cancelled = false;

    async function fetch() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksData(abortController.signal);
        if (!cancelled) setData(result);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? 'Failed to load decks');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetch();
    return () => { cancelled = true; abortController.abort(); };
  }, []);

  return { data, loading, error };
}
