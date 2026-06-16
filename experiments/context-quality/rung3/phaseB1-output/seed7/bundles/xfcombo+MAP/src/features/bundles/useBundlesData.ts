import { useEffect, useState } from 'react';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';

interface UseBundlesDataResult {
    bundles: BundleDto[];
    total: number;
    loading: boolean;
    error: string | null;
}

export function useBundlesData(): UseBundlesDataResult {
    const [bundles, setBundles] = useState<BundleDto[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function fetchBundles() {
            setLoading(true);
            setError(null);

            try {
                const response = await api.getBundles({ page: 0, size: 100 });
                if (!cancelled) {
                    setBundles(response.data);
                    setTotal(response.total);
                }
            } catch (err) {
                if (!cancelled) {
                    const message = err instanceof Error ? err.message : 'Failed to load bundles';
                    setError(message);
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

    return { bundles, total, loading, error };
}
