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
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{formatUSDshort(deck.totalValue)}</span>
          <span className="mono xs muted">total value</span>
        </div>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{deck.cardCount}</span>
          <span className="mono xs muted">cards</span>
        </div>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{deck.uniqueCards}</span>
          <span className="mono xs muted">unique</span>
        </div>
      </div>
      {deck.topCardName && (
        <div className={s.topCard}>
          <span className="mono xs muted">Top card: </span>
          <span className="mono xs">{deck.topCardName}</span>
          <span className="mono xs muted"> · {formatUSDshort(deck.topCardValue)}</span>
        </div>
      )}
      <div className={`mono xs muted ${s.updated}`}>Updated {deck.lastUpdated}</div>
    </div>
  );
}
