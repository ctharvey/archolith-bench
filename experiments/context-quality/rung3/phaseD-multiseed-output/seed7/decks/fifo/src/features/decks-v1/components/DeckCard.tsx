import type { DeckV1 } from '../types';
import { setUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: DeckV1;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a
      href={setUrl(deck.id, deck.name)}
      className={css.deckCard}
      data-id={deck.id}
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
        <div className={css.statItem}>
          <span className={css.statLabel}>Cards</span>
          <span className={css.statValue}>{deck.cardCount}</span>
        </div>
        <div className={css.statItem}>
          <span className={css.statLabel}>Unique</span>
          <span className={css.statValue}>{deck.uniqueCards}</span>
        </div>
      </div>

      <div className={css.footer}>
        {deck.topCardImageUrl ? (
          <img className={css.topCard} src={deck.topCardImageUrl} alt="" />
        ) : (
          <div className={css.topCardPlaceholder}>◆</div>
        )}
        <span className={css.updated}>Updated {deck.updatedAt}</span>
      </div>
    </a>
  );
}
