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
      data-id={deck.id}
    >
      <div className={css.headerRow}>
        <div>
          <div className={css.name}>{deck.name}</div>
          <div className={css.meta}>{deck.format} · {deck.archetype}</div>
        </div>
        <div className={css.value}>{deck.totalValueFormatted}</div>
      </div>

      <div className={css.statsRow}>
        <div className={css.stat}>
          <span className={css.statLabel}>Cards</span>
          <span>{deck.cardCount}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Win Rate</span>
          <span>{deck.winRate}</span>
        </div>
        <div className={css.stat}>
          <span className={css.statLabel}>Popularity</span>
          <span>{deck.popularity}</span>
        </div>
      </div>

      <div className={css.colorBar} style={{ background: deck.color }} />
    </a>
  );
}
