import { formatUSDshort } from '@/domain/formatters';
import type { Deck } from '../types';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: Deck;
}

export default function DeckTile({ deck }: DeckTileProps) {
  return (
    <div className={`set-tile ${s.tile}`}>
      <div className={s.header}>
        <span className={s.name}>{deck.name}</span>
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono xs muted">Market value</span>
          <span className={`mono ${s.value}`}>{formatUSDshort(deck.totalValue)}</span>
        </div>
        <div className={s.stat}>
          <span className="mono xs muted">Cards</span>
          <span className="mono">{deck.cardCount}</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards:</span>
          <span className="mono xs">{deck.topCards.slice(0, 3).join(', ')}</span>
        </div>
      )}
      <div className={`mono xs muted ${s.updated}`}>
        Updated {new Date(deck.lastUpdated).toLocaleDateString()}
      </div>
    </div>
  );
}
