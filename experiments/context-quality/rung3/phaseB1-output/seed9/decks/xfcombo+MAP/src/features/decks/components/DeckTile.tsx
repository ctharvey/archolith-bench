import { formatUSDshort } from '@/domain/formatters';
import type { DeckData } from '../types';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: DeckData;
}

export default function DeckTile({ deck }: DeckTileProps) {
  return (
    <div className={`set-tile ${s.tile}`}>
      <div className={s.header}>
        <span className={s.name}>{deck.name}</span>
        <span className={`mono xs muted`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{formatUSDshort(deck.totalValue)}</span>
          <span className="mono xs muted">Total Value</span>
        </div>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{deck.cardCount}</span>
          <span className="mono xs muted">Cards</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards:</span>
          <div className={s.cardList}>
            {deck.topCards.slice(0, 3).map((card, i) => (
              <span key={i} className={`mono xs ${s.cardItem}`}>
                {card.name} ({formatUSDshort(card.price)})
              </span>
            ))}
          </div>
        </div>
      )}
      <div className={`mono xs muted ${s.updated}`}>
        Updated: {deck.lastUpdated ? new Date(deck.lastUpdated).toLocaleDateString() : '—'}
      </div>
    </div>
  );
}
