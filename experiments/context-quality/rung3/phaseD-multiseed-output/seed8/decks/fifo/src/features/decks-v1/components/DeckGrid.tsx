import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
  totalDecks: number;
  totalValue: number;
}

export default function DeckGrid({ decks, totalDecks, totalValue }: DeckGridProps) {
  const formattedTotal = totalValue >= 1000
    ? `$${(totalValue / 1000).toFixed(1)}k`
    : `$${totalValue.toFixed(2)}`;

  return (
    <div>
      <div className={css.header}>
        <div>
          <h2 className={css.title}>Decks</h2>
          <div className={css.subtitle}>Browse all tracked decks</div>
        </div>
        <div className={css.statsRow}>
          <div>
            <span className={css.statValue}>{totalDecks}</span> decks
          </div>
          <div>
            <span className={css.statValue}>{formattedTotal}</span> total value
          </div>
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
