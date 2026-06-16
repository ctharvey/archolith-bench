import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  cards: PromoCard[];
}

export default function PromoGrid({ cards }: PromoGridProps) {
  const [yearFilter, setYearFilter] = useState<number | null>(null);

  const years = useMemo(() => {
    const yearSet = new Set(cards.map(c => c.year).filter(y => y > 0));
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [cards]);

  const filtered = useMemo(() => {
    if (yearFilter === null) return cards;
    return cards.filter(c => c.year === yearFilter);
  }, [cards, yearFilter]);

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Promo Cards</h2>
        <span className={css.count}>{filtered.length} cards</span>
      </div>

      {years.length > 1 && (
        <div className="row" style={{ gap: 8, padding: '0 14px', marginBottom: 12, flexWrap: 'wrap' }}>
          <button
            className={`pill ${yearFilter === null ? 'active' : ''}`}
            onClick={() => setYearFilter(null)}
          >
            All Years
          </button>
          {years.map(year => (
            <button
              key={year}
              className={`pill ${yearFilter === year ? 'active' : ''}`}
              onClick={() => setYearFilter(year)}
            >
              {year}
            </button>
          ))}
        </div>
      )}

      {filtered.length === 0 ? (
        <div className={css.empty}>No promo cards found.</div>
      ) : (
        <div className={css.grid}>
          {filtered.map(card => (
            <PromoCard key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}
