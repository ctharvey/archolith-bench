import { useEffect, useState } from 'react';
import { loadV3DecksData } from '../adapter';
import type { DecksV3Deck } from '../types';
import DeckGrid from './DeckGrid';
import s from './DeckBrowseScreen.module.css';

export default function DeckBrowseScreen() {
  const [decks, setDecks] = useState<DecksV3Deck[]>([]);
  const [totalDecks, setTotalDecks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await loadV3DecksData(controller.signal);
        setDecks(data.decks);
        setTotalDecks(data.totalDecks);
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError('Failed to load decks. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className={s.browseScreen}>
        <div className={s.loading}>Loading decks...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.browseScreen}>
        <div className={s.error}>{error}</div>
      </div>
    );
  }

  return (
    <div className={s.browseScreen}>
      <h1 className={s.pageTitle}>Browse Decks</h1>
      <p className={s.pageSubtitle}>Explore deck market values and compositions</p>
      <DeckGrid decks={decks} totalDecks={totalDecks} />
    </div>
  );
}
