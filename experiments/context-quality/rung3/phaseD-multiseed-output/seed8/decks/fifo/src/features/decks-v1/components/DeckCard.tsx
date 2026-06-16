import type { DeckV1 } from '../types';
import { deckUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: DeckV1;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a href={deckUrl(deck.id, deck.name)} className={css.card}>
      <div className={css.header}>
        <div>
          <h3 className={css.name}>{deck.name}</h3>
          <div className={css.meta}>
            {deck.format} · {deck.archetype}
          </div>
        </div>
        <div className={css.value}>{deck.totalValueFormatted}</div>
      </div>

      <div className={css.stats}>
        <div className={css.stat}>
          <span className={css.statLabel}>Cards</span>
          <span>{deck.cardCount}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Unique</span>
          <span>{deck.uniqueCards}</span>
        </div>
        {deck.topCardName && (
          <div className={css.stat}>
            <span className={css.statLabel}>Top</span>
            <span>{deck.topCardName}</span>
          </div>
        )}
      </div>

      <div
        className={css.colorBar}
        style={{ background: deck.color }}
      />
    </a>
  );
}
