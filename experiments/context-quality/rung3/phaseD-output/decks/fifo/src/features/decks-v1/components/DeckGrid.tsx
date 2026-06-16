import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
  totalValue: number;
}

export default function DeckGrid({ decks, totalValue }: DeckGridProps) {
  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Browse Decks</h2>
        <div className={css.totalValue}>
          Total market value: <strong>${totalValue.toLocaleString()}</strong>
        </div>
      </div>
      <div className={css.grid}>
        {decks.map(deck => (
          <DeckCard key={deck.id} deck={deck} />
        ))}
      </div>
    </div>
  );
}
