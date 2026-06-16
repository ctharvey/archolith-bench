import { useEffect, useMemo, useState } from 'react';
import { loadDecksData } from './adapter';
import type { DeckItem } from './types';

export function useDecksData() {
  const [decks, setDecks] = useState<DeckItem[]>([]);
  const [stats, setStats] = useState({ totalDecks: 0, totalMarketValue: 0, avgDeckValue: 0, biggestDeck: null as string | null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('value');

  useEffect(() => {
    const ac = new AbortController();
    loadDecksData(ac.signal)
      .then(d => {
        if (!ac.signal.aborted) {
          setDecks(d.decks);
          setStats({ totalDecks: d.totalDecks, totalMarketValue: d.totalMarketValue, avgDeckValue: d.avgDeckValue, biggestDeck: d.biggestDeck });
          setLoading(false);
        }
      })
      .catch(e => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        if (!ac.signal.aborted) { setError(e instanceof Error ? e.message : 'Failed'); setLoading(false); }
      });
    return () => { ac.abort(); };
  }, []);

  const filtered = useMemo(() => {
    let r = [...decks];
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(d => d.setName.toLowerCase().includes(q) || (d.serieName ?? '').toLowerCase().includes(q));
    }
    r.sort((a, b) => {
      if (sort === 'value') return (b.totalValue ?? 0) - (a.totalValue ?? 0);
      if (sort === 'cards') return b.cardCount - a.cardCount;
      if (sort === 'avg') return (b.avgFmv ?? 0) - (a.avgFmv ?? 0);
      if (sort === 'name') return a.setName.localeCompare(b.setName);
      if (sort === 'delta') return (b.delta7d ?? 0) - (a.delta7d ?? 0);
      return 0;
    });
    return r;
  }, [decks, search, sort]);

  return { decks: filtered, stats, loading, error, search, setSearch, sort, setSort };
}
