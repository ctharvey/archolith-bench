import type { Deck } from '../types';
import { deckUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: Deck;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a
      href={deckUrl(deck.id, deck.name)}
      className={css.deckCard}
      data-deck-id={deck.id}
    >
      <div className={css.colorAccent} style={{ background: deck.color }} />
      
      <div className={css.headerRow}>
        <div className={css.nameSection}>
          <h3 className={css.deckName}>{deck.name}</h3>
          <span className={css.formatBadge}>{deck.format}</span>
        </div>
        <div className={css.valueDisplay}>
          <div className={css.valueLabel}>Total Value</div>
          <div className={css.valueAmount}>{deck.totalValueFormatted}</div>
        </div>
      </div>

      <div className={css.statsRow}>
        <span className={css.stat}>
          <span className={css.statIcon}>🃏</span>
          {deck.cardCount} cards
        </span>
        <span className={css.stat}>
          <span className={css.statIcon}>✦</span>
          {deck.uniqueCards} unique
        </span>
      </div>

      {deck.topCardName && (
        <div className={css.topCardSection}>
          {deck.topCardImageUrl ? (
            <img
              className={css.topCardImage}
              src={deck.topCardImageUrl}
              alt={deck.topCardName}
              loading="lazy"
            />
          ) : (
            <div className={css.topCardImage} style={{ background: deck.color }} />
          )}
          <div className={css.topCardInfo}>
            <div className={css.topCardLabel}>Top Card</div>
            <div className={css.topCardName}>{deck.topCardName}</div>
            <div className={css.topCardValue}>
              {new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }).format(deck.topCardValue)}
            </div>
          </div>
        </div>
      )}
    </a>
  );
}
