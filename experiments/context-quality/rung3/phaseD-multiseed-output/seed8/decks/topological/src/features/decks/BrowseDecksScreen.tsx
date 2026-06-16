import React, { useEffect, useState } from 'react';
import { fetchDecks } from './api';
import { toDeckDisplayList } from './mappers';
import { DeckList } from './DeckList';
import { PageMain, PageTitle } from '@/ui/layout';
import type { DeckDisplay } from './types';

export function BrowseDecksScreen() {
  const [decks, setDecks] = useState<DeckDisplay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const dtos = await fetchDecks();
        if (!cancelled) {
          setDecks(toDeckDisplayList(dtos));
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load decks');
          setLoading(false);
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <div className="error-state">{error}</div>
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Decks</PageTitle>
      <DeckList decks={decks} loading={loading} />
    </PageMain>
  );
}
