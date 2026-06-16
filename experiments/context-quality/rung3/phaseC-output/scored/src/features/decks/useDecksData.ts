import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';

interface UseDecksDataReturn {
    decks: DeckDto[];
    total: number;
    loading: boolean;
    loadingMore: boolean;
    hasMore: boolean;
    loadMore: () => void;
    error: string | null;
}

export function useDecksData(): UseDecksDataReturn {
    const [decks, setDecks] = useState<DeckDto[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const pageRef = useRef(0);
    const abortRef = useRef<AbortController | null>(null);

    const fetchDecks = useCallback(async (page: number, append: boolean) => {
        abortRef.current?.abort();
        const ac = new AbortController();
        abortRef.current = ac;

        if (page === 0) {
            setLoading(true);
        } else {
            setLoadingMore(true);
        }
        setError(null);

        try {
            const res = await api.getDecks({ page, size: 24 }, ac.signal);
            if (ac.signal.aborted) return;

            setDecks(prev => append ? [...prev, ...res.data] : res.data);
            setTotal(res.total);
            pageRef.current = page;
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            setError(err instanceof Error ? err.message : 'Failed to load decks');
        } finally {
            if (!ac.signal.aborted) {
                setLoading(false);
                setLoadingMore(false);
            }
        }
    }, []);

    useEffect(() => {
        fetchDecks(0, false);
        return () => { abortRef.current?.abort(); };
    }, [fetchDecks]);

    const hasMore = decks.length < total;

    const loadMore = useCallback(() => {
        if (!loadingMore && hasMore) {
            fetchDecks(pageRef.current + 1, true);
        }
    }, [loadingMore, hasMore, fetchDecks]);

    return { decks, total, loading, loadingMore, hasMore, loadMore, error };
}
