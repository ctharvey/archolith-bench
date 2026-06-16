import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
}

export default function DeckGrid({ decks }: DeckGridProps) {
  if (decks.length === 0) {
    return (
      <div className={css.grid}>
        <div className={css.empty}>No decks found</div>
      </div>
    );
  }

  return (
    <div className={css.grid}>
      {decks.map(deck => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </div>
  );
}
