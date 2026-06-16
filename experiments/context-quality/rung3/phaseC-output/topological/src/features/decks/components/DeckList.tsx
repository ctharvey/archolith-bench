import React from 'react';
import type { DeckDto } from '../types';
import { DeckCard } from './DeckCard';
import { Grid } from '@/ui/layout';

interface DeckListProps {
  decks: DeckDto[];
}

export const DeckList: React.FC<DeckListProps> = ({ decks }) => {
  return (
    <Grid className="deck-list">
      {decks.map((deck) => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </Grid>
  );
};
