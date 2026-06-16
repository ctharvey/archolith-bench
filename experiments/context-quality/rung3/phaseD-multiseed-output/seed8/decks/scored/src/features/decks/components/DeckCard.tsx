import { formatUSDshort } from '@/domain/formatters';
import type { DeckSummary } from '../types';
import s from './DeckCard.module.css';

interface DeckCardProps {
  deck: DeckSummary;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <div className={s.card}>
      <div className={s.header}>
        <h3 className={s.name}>{deck.name}</h3>
        <span className={s.format}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className={s.statLabel}>Value</span>
          <span className={s.statValue}>{formatUSDshort(deck.totalValue)}</span>
        </div>
        <div className={s.stat}>
          <span className={s.statLabel}>Cards</span>
          <span className={s.statValue}>{deck.cardCount}</span>
        </div>
      </div>
      {deck.topCards.length > 0 && (
        <div className={s.topCards}>
          <span className={s.topCardsLabel}>Top cards:</span>
          <span className={s.topCardsList}>{deck.topCards.slice(0, 3).join(', ')}</span>
        </div>
      )}
      <div className={s.footer}>
        <span className={s.updated}>Updated {new Date(deck.lastUpdated).toLocaleDateString()}</span>
      </div>
    </div>
  );
}
