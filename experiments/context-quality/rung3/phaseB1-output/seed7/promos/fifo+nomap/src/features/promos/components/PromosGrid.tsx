import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromosGrid.module.css';

interface PromosGridProps {
  promos: PromoCard[];
}

export default function PromosGrid({ promos }: PromosGridProps) {
  const [search, setSearch] = useState('');
  const [yearFilter, setYearFilter] = useState('all');

  const years = useMemo(() => {
    const y = new Set(promos.map(p => p.year).filter(Boolean));
    return Array.from(y).sort((a, b) => b - a);
  }, [promos]);

  const filtered = useMemo(() => {
    return promos.filter(p => {
      if (yearFilter !== 'all' && p.year !== Number(yearFilter)) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          p.id.toLowerCase().includes(q) ||
          p.set.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [promos, search, yearFilter]);

  return (
    <div>
      <div className={css.header}>
        <div className={css.title}>Promos</div>
        <div className={css.count}>{filtered.length} cards</div>
      </div>

      <div className={css.filters}>
        <input
          className={css.searchInput}
          placeholder="Search promos…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className={css.yearFilter}>
          <select
            className={css.yearSelect}
            value={yearFilter}
            onChange={e => setYearFilter(e.target.value)}
          >
            <option value="all">All years</option>
            {years.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <div className={css.grid}>
        {filtered.map(promo => (
          <PromoCard key={promo.id} promo={promo} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--t-4)' }}>
          No promos found matching your filters.
        </div>
      )}
    </div>
  );
}
