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
      <div className={css.contentLayer}>
        <div className={css.topRow}>
          <div
            className={css.symbol}
            style={{ background: deck.color }}
          >
            {deck.sym}
          </div>
          <div className={css.infoCol}>
            <div className={css.headerRow}>
              <div>
                <h3 className={css.name}>{deck.name}</h3>
                <div className={css.meta}>
                  {deck.format} · {deck.archetype}
                </div>
              </div>
              <div className={css.value}>{deck.totalValueFormatted}</div>
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
              <div className={css.stat}>
                <span className={css.statLabel}>Updated</span>
                <span className={css.statValue}>{deck.updatedAt}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a>
  );
}
