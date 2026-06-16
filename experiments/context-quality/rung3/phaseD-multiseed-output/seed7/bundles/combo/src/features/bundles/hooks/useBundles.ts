import { useState, useEffect } from 'react';
import type { SealedProductPriceDto } from '@/data/apiClient';
import { api } from '@/data/apiClient';

interface UseBundlesResult {
  bundles: SealedProductPriceDto[];
  loading: boolean;
  error: string | null;
}

export function useBundles(): UseBundlesResult {
  const [bundles, setBundles] = useState<SealedProductPriceDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchBundles() {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getSealedBundles();
        if (!cancelled) {
          setBundles(data ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load bundles');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchBundles();

    return () => {
      cancelled = true;
    };
  }, []);

  return { bundles, loading, error };
}
