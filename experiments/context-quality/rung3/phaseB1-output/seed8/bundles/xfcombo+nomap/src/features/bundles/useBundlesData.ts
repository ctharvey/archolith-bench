import { useEffect, useState } from 'react';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';

export function useBundlesData() {
    const [bundles, setBundles] = useState<BundleDto[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        api.getBundles()
            .then(res => {
                if (cancelled) return;
                setBundles(res.data);
                setLoading(false);
            })
            .catch(err => {
                if (cancelled) return;
                setError(err.message || 'Failed to load bundles');
                setLoading(false);
            });

        return () => { cancelled = true; };
    }, []);

    return { bundles, loading, error };
}
