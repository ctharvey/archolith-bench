import { formatUSDshort } from '@/domain/formatters';
import type { DeckSummary } from '../types';
import s from './DeckCard.module.css';

interface DeckCardProps {
  deck: DeckSummary;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <div className={`set-tile ${s.card}`}>
      <div className={s.header}>
        <span className={s.name}>{deck.name}</span>
        <span className={`mono xs muted ${s.format}`}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{formatUSDshort(deck.totalValue)}</span>
          <span className="mono xs muted">Total value</span>
        </div>
        <div className={s.stat}>
          <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{deck.cardCount}</span>
          <span className="mono xs muted">Cards</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className="mono xs muted">Top cards: </span>
          <span className="mono xs">{deck.topCards.join(', ')}</span>
        </div>
      )}
      <div className={`mono xs muted ${s.updated}`}>
        Updated: {deck.lastUpdated ? new Date(deck.lastUpdated).toLocaleDateString() : 'N/A'}
      </div>
    </div>
  );
}
