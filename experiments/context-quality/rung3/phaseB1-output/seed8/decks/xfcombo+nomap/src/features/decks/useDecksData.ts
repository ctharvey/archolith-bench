import { useEffect, useState } from 'react';
import { api } from '@/data/apiClient';
import type { DecksPageData } from './types';
import { loadDecksData } from './adapter';

export function useDecksData() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function fetch() {
      try {
        setLoading(true);
        setError(null);
        const result = await loadDecksData(controller.signal);
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

    fetch();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  return { data, loading, error };
}
