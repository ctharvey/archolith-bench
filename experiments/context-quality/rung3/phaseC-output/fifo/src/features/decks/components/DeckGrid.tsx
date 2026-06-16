import type { Deck } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: Deck[];
  totalValue: number;
}

export default function DeckGrid({ decks, totalValue }: DeckGridProps) {
  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Decks</h2>
        <span className={css.totalValue}>
          Total Market Value: ${totalValue.toLocaleString()}
        </span>
      </div>
      <div className={css.grid}>
        {decks.map(deck => (
          <DeckCard key={deck.id} deck={deck} />
        ))}
      </div>
    </div>
  );
}
