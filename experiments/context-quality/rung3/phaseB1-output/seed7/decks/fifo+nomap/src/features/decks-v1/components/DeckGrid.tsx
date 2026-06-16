import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}

export default function DeckGrid({ decks, totalDecks, totalValue, avgValue }: DeckGridProps) {
  return (
    <div className={css.container}>
      <div className={css.header}>
        <h2 className={css.title}>Decks</h2>
        <div className={css.stats}>
          <span>
            Total: <span className={css.statValue}>{totalDecks}</span>
          </span>
          <span>
            Value: <span className={css.statValue}>${totalValue.toFixed(2)}</span>
          </span>
          <span>
            Avg: <span className={css.statValue}>${avgValue.toFixed(2)}</span>
          </span>
        </div>
      </div>

      {decks.length === 0 ? (
        <div className={css.empty}>No decks found</div>
      ) : (
        <div className={css.grid}>
          {decks.map(deck => (
            <DeckCard key={deck.id} deck={deck} />
          ))}
        </div>
      )}
    </div>
  );
}
