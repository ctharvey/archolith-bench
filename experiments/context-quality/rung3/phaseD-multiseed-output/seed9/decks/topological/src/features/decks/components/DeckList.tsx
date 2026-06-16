import type { DeckDto } from '../types';
import { DeckCard } from './DeckCard';
import { Grid, EmptyState } from '@/ui';

interface DeckListProps {
  decks: DeckDto[];
}

export function DeckList({ decks }: DeckListProps) {
  if (decks.length === 0) {
    return <EmptyState message="No decks found." />;
  }

  return (
    <Grid>
      {decks.map((deck) => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </Grid>
  );
}
