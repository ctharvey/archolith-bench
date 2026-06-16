import { formatUSDshort } from '@/domain/formatters';
import type { DeckItem } from '../types';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: DeckItem;
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
          <span className="mono xs muted">Value</span>
          <span className="mono" style={{ fontWeight: 700 }}>{formatUSDshort(deck.totalValue)}</span>
        </div>
        <div className={s.stat}>
          <span className="mono xs muted">Cards</span>
          <span className="mono">{deck.cardCount}</span>
        </div>
      </div>
      <div className={`mono xs muted ${s.updated}`}>
        Updated {new Date(deck.updatedAt).toLocaleDateString()}
      </div>
    </div>
  );
}
