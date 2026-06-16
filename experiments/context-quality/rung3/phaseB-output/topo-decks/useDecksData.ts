import { useEffect, useState } from 'react';
import { repo } from '@/data/repository';
import type { Deck } from '@/domain/models';

export function useDecksData() {
    const [decks, setDecks] = useState<Deck[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const ac = new AbortController();
        repo.decks.all(ac.signal)
            .then(data => {
                if (!ac.signal.aborted) {
                    setDecks(data);
                    setLoading(false);
                }
            })
            .catch(err => {
                if (err instanceof DOMException && err.name === 'AbortError') return;
                if (!ac.signal.aborted) { setError(err instanceof Error ? err.message : 'Failed to load'); setLoading(false); }
            });
        return () => { ac.abort(); };
    }, []);

    return { decks, loading, error };
}
