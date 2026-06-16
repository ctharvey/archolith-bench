import type { DeckV1 } from '../types';
import s from './DeckStats.module.css';

interface DeckStatsProps {
  decks: DeckV1[];
  totalMarketValue: number;
}

export default function DeckStats({ decks, totalMarketValue }: DeckStatsProps) {
  const avgValue = decks.length > 0 ? totalMarketValue / decks.length : 0;
  const maxValue = Math.max(...decks.map(d => d.totalValue), 0);
  const totalCards = decks.reduce((a, d) => a + d.cardCount, 0);

  return (
    <div className={s.container}>
      <div className={`row ${s.headerRow}`}>
        <div className={`row ${s.titleGroup}`}>
          <h2 className={s.labelNoMargin}>Deck Market Overview</h2>
        </div>
      </div>
      <div className={s.statCards}>
        <div className={s.statCard}>
          <span className={s.statLabel}>Total Decks</span>
          <span className={s.statValue}>{decks.length}</span>
        </div>
        <div className={s.statCard}>
          <span className={s.statLabel}>Total Market Value</span>
          <span className={s.statValue}>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            }).format(totalMarketValue)}
          </span>
        </div>
        <div className={s.statCard}>
          <span className={s.statLabel}>Average Value</span>
          <span className={s.statValue}>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 2,
            }).format(avgValue)}
          </span>
        </div>
        <div className={s.statCard}>
          <span className={s.statLabel}>Highest Value</span>
          <span className={s.statValue}>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 2,
            }).format(maxValue)}
          </span>
        </div>
        <div className={s.statCard}>
          <span className={s.statLabel}>Total Cards</span>
          <span className={s.statValue}>{totalCards.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}
