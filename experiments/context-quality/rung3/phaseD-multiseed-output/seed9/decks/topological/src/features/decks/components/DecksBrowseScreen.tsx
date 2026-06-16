import { useEffect, useState } from 'react';
import { loadDecksData } from '../api';
import type { DecksPageData } from '../types';
import { DeckList } from './DeckList';
import { PageMain, PageTitle, SkeletonRow } from '@/ui';

export function DecksBrowseScreen() {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    loadDecksData()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load decks');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <SkeletonRow count={6} />
      </PageMain>
    );
  }

  if (error) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <p className="error-message">{error}</p>
      </PageMain>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <PageMain>
      <PageTitle>Decks</PageTitle>
      <p className="decks-count">{data.totalDecks} decks</p>
      <DeckList decks={data.decks} />
    </PageMain>
  );
}
