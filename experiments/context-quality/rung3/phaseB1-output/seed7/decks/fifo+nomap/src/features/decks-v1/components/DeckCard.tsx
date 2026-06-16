import type { DeckV1 } from '../types';
import { deckUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: DeckV1;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a
      href={deckUrl(deck.id, deck.name)}
      className={css.card}
      data-deck-id={deck.id}
    >
      <div className={css.colorBar} style={{ background: deck.color }} />

      <div className={css.header}>
        <div>
          <h3 className={css.name}>{deck.name}</h3>
          <div className={css.meta}>
            <span>{deck.format}</span>
            <span>·</span>
            <span>{deck.archetype}</span>
          </div>
        </div>
        <div className={css.value}>{deck.totalValueFormatted}</div>
      </div>

      <div className={css.stats}>
        <div className={css.statItem}>
          <span className={css.statLabel}>Cards</span>
          <span>{deck.cardCount}</span>
        </div>
        <div className={css.statItem}>
          <span className={css.statLabel}>Unique</span>
          <span>{deck.uniqueCards}</span>
        </div>
      </div>

      {deck.topCardImageUrl && deck.topCardName && (
        <div className={css.topCard}>
          <img
            className={css.topCardImage}
            src={deck.topCardImageUrl}
            alt={deck.topCardName}
            loading="lazy"
          />
          <div className={css.topCardInfo}>
            <div className={css.topCardName}>{deck.topCardName}</div>
            {deck.topCardValue != null && (
              <div className={css.topCardValue}>
                ${deck.topCardValue.toFixed(2)}
              </div>
            )}
          </div>
        </div>
      )}

      <div className={css.updated}>Updated {deck.updatedAt}</div>
    </a>
  );
}
