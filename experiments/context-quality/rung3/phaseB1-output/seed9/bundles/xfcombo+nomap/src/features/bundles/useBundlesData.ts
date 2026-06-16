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

        api.getBundles({ page: 0, size: 100 })
            .then(res => {
                if (cancelled) return;
                setBundles(res.data);
                setTotal(res.total);
                setLoading(false);
            })
            .catch(err => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : 'Failed to load bundles');
                setLoading(false);
            });

        return () => { cancelled = true; };
    }, []);

    return { bundles, total, loading, error };
}
