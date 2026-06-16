import React, { useEffect, useState } from 'react';
import { PageMain, PageTitle, Grid, SkeletonRow, EmptyState } from '@/ui';
import { fetchDecks } from './api';
import { mapDeckToDisplay } from './mappers';
import { DeckCard } from './DeckCard';
import type { DeckDisplay } from './mappers';

export function DecksBrowseScreen() {
  const [decks, setDecks] = useState<DeckDisplay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDecks()
      .then((data) => {
        if (!cancelled) {
          setDecks(data.map(mapDeckToDisplay));
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load decks');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
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
        <EmptyState
          title="Error loading decks"
          description={error}
          action={{ label: 'Retry', onClick: () => window.location.reload() }}
        />
      </PageMain>
    );
  }

  if (decks.length === 0) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <EmptyState
          title="No decks found"
          description="There are no decks to display yet."
        />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Decks</PageTitle>
      <Grid>
        {decks.map((deck) => (
          <DeckCard key={deck.id} deck={deck} />
        ))}
      </Grid>
    </PageMain>
  );
}
