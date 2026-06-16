import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import s from './PromoGrid.module.css';

interface PromoGridProps {
  promos: PromoCard[];
  years: number[];
}

export default function PromoGrid({ promos, years }: PromoGridProps) {
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  const filtered = useMemo(() => {
    if (selectedYear === null) return promos;
    return promos.filter(p => p.year === selectedYear);
  }, [promos, selectedYear]);

  return (
    <div className={s.container}>
      <div className={s.header}>
        <h2 className={s.title}>Promos</h2>
        <span className={s.count}>{filtered.length} cards</span>
      </div>

      <div className={s.filters}>
        <button
          className={`${s.filterPill} ${selectedYear === null ? s.filterPillActive : ''}`}
          onClick={() => setSelectedYear(null)}
        >
          All Years
        </button>
        {years.map(year => (
          <button
            key={year}
            className={`${s.filterPill} ${selectedYear === year ? s.filterPillActive : ''}`}
            onClick={() => setSelectedYear(year)}
          >
            {year}
          </button>
        ))}
      </div>

      <div className={s.grid}>
        {filtered.length > 0 ? (
          filtered.map(promo => (
            <PromoCard key={promo.id} promo={promo} />
          ))
        ) : (
          <div className={s.empty}>
            No promo cards found for this year.
          </div>
        )}
      </div>
    </div>
  );
}
