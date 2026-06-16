import type { DecksV1Deck } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DecksV1Deck[];
  totalValue: number;
}

function formatTotalValue(value: number): string {
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}k`;
  }
  return `$${value.toFixed(2)}`;
}

export default function DeckGrid({ decks, totalValue }: DeckGridProps) {
  return (
    <div className={css.container}>
      <div className={css.headerRow}>
        <div className={css.titleGroup}>
          <h2 className={css.title}>Decks</h2>
          <span className={css.totalValue}>
            Total value: {formatTotalValue(totalValue)}
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
