import { formatUSDshort } from '@/domain/formatters';
import type { Deck } from '../types';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: Deck;
}

export default function DeckTile({ deck }: DeckTileProps) {
  return (
    <div className={s.tile}>
      <div className={s.tileHeader}>
        <h3 className={s.deckName}>{deck.name}</h3>
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.tileBody}>
        <div className={s.stat}>
          <span className="mono xs muted">Market value</span>
          <span className={`mono ${s.value}`}>{formatUSDshort(deck.totalValue)}</span>
        </div>
        <div className={s.stat}>
          <span className="mono xs muted">Cards</span>
          <span className={`mono ${s.count}`}>{deck.cardCount}</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards:</span>
          <span className="mono xs">{deck.topCards.slice(0, 3).join(', ')}</span>
        </div>
      )}
      <div className={s.tileFooter}>
        <span className="mono xs muted">Updated {deck.lastUpdated}</span>
      </div>
    </div>
  );
}
