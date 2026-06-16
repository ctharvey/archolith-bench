import React from 'react';
import type { Deck } from '../types';
import { DeckCard } from './DeckCard';
import { Grid, EmptyState } from '@/ui';

interface DeckListProps {
  decks: Deck[];
  loading?: boolean;
}

export const DeckList: React.FC<DeckListProps> = ({ decks, loading }) => {
  if (loading) {
    return (
      <Grid>
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
    <Grid>
      {decks.map((deck) => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </Grid>
  );
};
