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
      className={css.deckCard}
      data-deck-id={deck.id}
    >
      <div className={css.colorBar} style={{ background: deck.color }} />

      <div className={css.headerRow}>
        <div className={css.nameGroup}>
          <h3 className={css.name}>{deck.name}</h3>
          <div className={css.meta}>
            {deck.format} · {deck.archetype}
          </div>
        </div>
        <div className={css.valueBadge}>{deck.totalValueFormatted}</div>
      </div>

      <div className={css.statsRow}>
        <div className={css.stat}>
          <span className={css.statLabel}>Cards</span>
          <span className={css.statValue}>{deck.cardCount}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Unique</span>
          <span className={css.statValue}>{deck.uniqueCards}</span>
        </div>
      </div>

      {deck.topCardName && (
        <div className={css.topCard}>
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
            <div className={css.topCardName}>{deck.topCardName}</div>
            <div className={css.topCardValue}>
              Top card: ${deck.topCardValue.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      <div className={css.updatedAt}>
        Updated {new Date(deck.updatedAt).toLocaleDateString()}
      </div>
    </a>
  );
}
