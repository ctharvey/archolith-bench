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
        <h3 className={s.name}>{deck.name}</h3>
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{formatUSDshort(deck.totalValue)}</span>
          <span className="mono xs muted">market value</span>
        </div>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{deck.cardCount}</span>
          <span className="mono xs muted">cards</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards:</span>
          <div className={s.cardList}>
            {deck.topCards.slice(0, 3).map((card, i) => (
              <div key={i} className={`mono xs ${s.cardItem}`}>
                {card.quantity}x {card.name} — {formatUSDshort(card.price)}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className={`mono xs muted ${s.updated}`}>
        Updated {new Date(deck.updatedAt).toLocaleDateString()}
      </div>
    </div>
  );
}
