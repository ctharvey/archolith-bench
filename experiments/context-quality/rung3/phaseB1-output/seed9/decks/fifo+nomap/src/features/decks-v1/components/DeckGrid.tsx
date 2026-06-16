import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import s from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
}

export default function DeckGrid({ decks }: DeckGridProps) {
  if (decks.length === 0) {
    return (
      <div className={s.grid}>
        <div className={s.empty}>No decks found matching your criteria.</div>
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {decks.map(deck => (
        <DeckCard key={deck.id} deck={deck} />
      ))}
    </div>
  );
}
