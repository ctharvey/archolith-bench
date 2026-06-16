import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  promos: PromoCard[];
  totalPromos: number;
}

export default function PromoGrid({ promos, totalPromos }: PromoGridProps) {
  const [yearFilter, setYearFilter] = useState<string>('all');

  const years = useMemo(() => {
    const yearSet = new Set(promos.map(p => p.year));
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [promos]);

  const filtered = useMemo(() => {
    if (yearFilter === 'all') return promos;
    return promos.filter(p => p.year === parseInt(yearFilter, 10));
  }, [promos, yearFilter]);

  return (
    <div>
      <div className={`box ${css.header}`}>
        <div className={css.title}>Promos</div>
        <div className={css.filterRow}>
          <span className={css.count}>{totalPromos} total</span>
          <select
            value={yearFilter}
            onChange={e => setYearFilter(e.target.value)}
            className={css.yearFilter}
          >
            <option value="all">All Years</option>
            {years.map(year => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </div>
      </div>
      <div className={css.grid}>
        {filtered.map(promo => (
          <PromoCard key={promo.id} promo={promo} />
        ))}
      </div>
    </div>
  );
}
