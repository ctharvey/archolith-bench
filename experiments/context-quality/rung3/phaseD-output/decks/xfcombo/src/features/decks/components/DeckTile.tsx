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
        <h3 className={s.name}>{deck.name}</h3>
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono xs muted">Cards</span>
          <span className="mono">{deck.totalCards}</span>
        </div>
        <div className={s.stat}>
          <span className="mono xs muted">Market Value</span>
          <span className="mono">{formatUSDshort(deck.marketValue)}</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards:</span>
          <div className={s.cardList}>
            {deck.topCards.slice(0, 3).map((card, i) => (
              <span key={i} className="mono xs">{card}</span>
            ))}
          </div>
        </div>
      )}
      <div className={s.footer}>
        <span className="mono xs muted">Updated {deck.lastUpdated}</span>
      </div>
    </div>
  );
}
