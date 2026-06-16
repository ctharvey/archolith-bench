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
    >
      <div className={css.colorBar} style={{ background: deck.color }} />

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
          <span className={css.statValue}>{deck.cardCount}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Unique</span>
          <span className={css.statValue}>{deck.uniqueCards}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Updated</span>
          <span className={css.statValue}>{deck.lastUpdated}</span>
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
            <span className={css.topCardName}>{deck.topCardName}</span>
            <span className={css.topCardValue}>
              Top card · {new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
              }).format(deck.topCardValue)}
            </span>
          </div>
        </div>
      )}
    </a>
  );
}
