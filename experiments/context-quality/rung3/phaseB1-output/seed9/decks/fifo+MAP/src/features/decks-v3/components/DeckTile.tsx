import type { DecksV3Deck } from '../types';
import { deckUrl } from '@/domain/slug';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: DecksV3Deck;
}

export default function DeckTile({ deck }: DeckTileProps) {
  return (
    <a
      href={deckUrl(deck.id, deck.name)}
      className={s.deckTile}
      data-id={deck.id}
    >
      <div className={s.headerRow}>
        <div className={s.deckName}>{deck.name}</div>
        <div className={s.formatBadge}>{deck.format}</div>
      </div>

      <div className={s.statsRow}>
        <div className={s.stat}>
          <span className={s.statLabel}>Total Value</span>
          <span className={`${s.statValue} ${s.valueHighlight}`}>{deck.totalValue}</span>
        </div>
        <div className={s.stat}>
          <span className={s.statLabel}>Cards</span>
          <span className={s.statValue}>{deck.cardCount}</span>
        </div>
        <div className={s.stat}>
          <span className={s.statLabel}>Unique</span>
          <span className={s.statValue}>{deck.uniqueCards}</span>
        </div>
      </div>

      <div className={s.topCardRow}>
        <span>
          Top card: <span className={s.topCardName}>{deck.topCardName}</span>
        </span>
        <span className={s.valueHighlight}>{deck.topCardValue}</span>
      </div>

      <div className={s.sym} style={{ background: deck.color }}>
        {deck.sym}
      </div>
    </a>
  );
}
