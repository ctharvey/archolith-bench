import type { DecksV1Deck } from '../types';
import { setUrl } from '@/domain/slug';
import css from './DeckCard.module.css';

interface DeckCardProps {
  deck: DecksV1Deck;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <a
      href={setUrl(deck.id, deck.name)}
      className={`clickable-link ${css.card}`}
    >
      <div className={css.colorBar} style={{ background: deck.color }} />
      
      <div className={css.cardInner}>
        <div className={css.imageContainer}>
          {deck.topCardImageUrl ? (
            <img
              className={css.cardImage}
              src={deck.topCardImageUrl}
              alt=""
              loading="lazy"
            />
          ) : (
            <div
              className={css.symbolPlaceholder}
              style={{ background: deck.color }}
            >
              {deck.sym}
            </div>
          )}
        </div>

        <div className={css.info}>
          <div className={css.header}>
            <div>
              <h3 className={css.name}>{deck.name}</h3>
              <div className={css.meta}>
                {deck.format} · {deck.archetype}
              </div>
            </div>
          </div>

          <div className={css.valueRow}>
            <div className={css.stat}>
              <span className={css.valueLabel}>Value</span>
              <span className={css.valueAmount}>{deck.totalValueFormatted}</span>
            </div>
            <div className={css.stat}>
              <span className={css.valueLabel}>Cards</span>
              <span>{deck.cardCount}</span>
            </div>
            <div className={css.stat}>
              <span className={css.valueLabel}>Unique</span>
              <span>{deck.uniqueCards}</span>
            </div>
          </div>
        </div>
      </div>
    </a>
  );
}
