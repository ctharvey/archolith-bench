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
      <div
        className={css.colorBar}
        style={{ background: deck.color }}
      />

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
        {deck.winRate && (
          <div className={css.stat}>
            <span className={css.statLabel}>Win Rate</span>
            <span>{deck.winRate}</span>
          </div>
        )}
      </div>

      <div className={css.badges}>
        {deck.tier && (
          <span className={`${css.badge} ${css.badgeTier}`}>
            Tier {deck.tier}
          </span>
        )}
        <span className={css.badge}>
          Updated {deck.updatedAt}
        </span>
      </div>

      {deck.topCardImageUrl && (
        <img
          className={css.cardImage}
          src={deck.topCardImageUrl}
          alt=""
          loading="lazy"
        />
      )}
    </a>
  );
}
