import { formatUSDshort } from '@/domain/formatters';
import type { Deck } from '../types';
import s from './DeckCard.module.css';

interface DeckCardProps {
  deck: Deck;
}

export default function DeckCard({ deck }: DeckCardProps) {
  return (
    <div className={s.card}>
      <div className={s.header}>
        <span className={s.name}>{deck.name}</span>
        <span className={s.format} style={{ color: deck.color }}>{deck.format}</span>
      </div>
      <div className={s.stats}>
        <div className={s.stat}>
          <span className={s.statValue}>{formatUSDshort(deck.totalValue)}</span>
          <span className={s.statLabel}>Value</span>
        </div>
        <div className={s.stat}>
          <span className={s.statValue}>{deck.cardCount}</span>
          <span className={s.statLabel}>Cards</span>
        </div>
      </div>
      <div className={s.footer}>
        <span className={s.updated}>Updated {deck.lastUpdated}</span>
      </div>
    </div>
  );
}
