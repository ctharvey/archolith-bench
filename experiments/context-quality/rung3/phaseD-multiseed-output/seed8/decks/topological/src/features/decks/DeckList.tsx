import React from 'react';
import type { DeckDisplay } from './types';
import { DeckCard } from './DeckCard';
import { Grid } from '@/ui/layout';
import { EmptyState } from '@/ui/feedback';

interface DeckListProps {
  decks: DeckDisplay[];
  loading?: boolean;
}

export function DeckList({ decks, loading }: DeckListProps) {
  if (loading) {
    return (
      <Grid cols={3} gap="md">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </Grid>
    );
  }

  if (decks.length === 0) {
    return <EmptyState message="No decks found" />;
  }

  return (
    <Grid cols={3} gap="md">
      {decks.map((deck) => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </Grid>
  );
}
