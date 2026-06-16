import { useEffect, useMemo, useState } from 'react';
import { loadDecksData } from './adapter';
import type { DeckItem } from './types';

export function useDecksV3Data() {
    const [decks, setDecks] = useState<DeckItem[]>([]);
    const [totalValue, setTotalValue] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState('all');
    const [sort, setSort] = useState('value');
    const [search, setSearch] = useState('');

    useEffect(() => {
        const ac = new AbortController();
        loadDecksData(ac.signal)
            .then(d => {
                if (!ac.signal.aborted) {
                    setDecks(d.decks);
                    setTotalValue(d.totalValue);
                    setLoading(false);
                }
            })
            .catch(e => {
                if (e instanceof DOMException && e.name === 'AbortError') return;
                if (!ac.signal.aborted) {
                    setError(e instanceof Error ? e.message : 'Failed to load');
                    setLoading(false);
                }
            });
        return () => { ac.abort(); };
    }, []);

    const filtered = useMemo(() => {
        let r = [...decks];
        if (filter === 'up') r = r.filter(d => d.d7Num > 0);
        else if (filter === 'dn') r = r.filter(d => d.d7Num < 0);
        else if (filter === 'flat') r = r.filter(d => d.d7Num === 0);
        if (search) {
            const q = search.toLowerCase();
            r = r.filter(d => d.name.toLowerCase().includes(q) || d.format.toLowerCase().includes(q) || d.setNames.some(s => s.toLowerCase().includes(q)));
        }
        r.sort((a, b) => {
            if (sort === 'value') return b.totalValue - a.totalValue;
            if (sort === 'delta') return b.d7Num - a.d7Num;
            if (sort === 'cards') return b.cardCount - a.cardCount;
            if (sort === 'name') return a.name.localeCompare(b.name);
            return 0;
        });
        return r;
    }, [decks, filter, sort, search]);

    const countUp = decks.filter(d => d.d7Num > 0).length;
    const countDn = decks.filter(d => d.d7Num < 0).length;
    const countFlat = decks.filter(d => d.d7Num === 0).length;

    const hotDecks = useMemo(() => {
        return [...decks].sort((a, b) => Math.abs(b.d7Num) - Math.abs(a.d7Num)).slice(0, 6);
    }, [decks]);

    return { decks: filtered, hotDecks, totalDecks: decks.length, totalValue, countUp, countDn, countFlat, loading, error, filter, setFilter, sort, setSort, search, setSearch };
}
