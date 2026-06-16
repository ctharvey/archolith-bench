import type { Deck } from '../types';
import { setUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: Deck;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a
      href={setUrl(deck.id, deck.name)}
      className={css.deckCard}
      style={{ '--accent': deck.color } as React.CSSProperties}
    >
      <div className={css.header}>
        <div>
          <h3 className={css.name}>{deck.name}</h3>
          <span className={css.format}>{deck.format}</span>
        </div>
        <div className={css.value}>{deck.totalValueFormatted}</div>
      </div>

      <div className={css.stats}>
        <div className={css.stat}>
          <span className={css.statLabel}>Cards</span>
          <span className={css.statValue}>{deck.cardCount}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Unique</span>
          <span className={css.statValue}>{deck.uniqueCards}</span>
        </div>
      </div>

      <div className={css.topCard}>
        {deck.topCardImageUrl ? (
          <img
            src={deck.topCardImageUrl}
            alt={deck.topCardName}
            className={css.topCardImage}
            loading="lazy"
          />
        ) : (
          <div className={css.topCardImage} style={{ background: deck.color }} />
        )}
        <div className={css.topCardInfo}>
          <span className={css.topCardLabel}>Top Card</span>
          <span className={css.topCardName}>{deck.topCardName}</span>
          <span className={css.topCardValue}>
            ${deck.topCardValue.toFixed(2)}
          </span>
        </div>
      </div>
    </a>
  );
}
