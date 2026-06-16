import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  promos: PromoCard[];
}

export default function PromoGrid({ promos }: PromoGridProps) {
  const [search, setSearch] = useState('');
  const [yearFilter, setYearFilter] = useState('all');

  const years = useMemo(() => {
    const ySet = new Set(promos.map(p => p.year).filter(y => y > 0));
    return Array.from(ySet).sort((a, b) => b - a);
  }, [promos]);

  const filtered = useMemo(() => {
    return promos.filter(p => {
      if (yearFilter !== 'all' && p.year !== parseInt(yearFilter, 10)) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          p.set.toLowerCase().includes(q) ||
          p.id.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [promos, search, yearFilter]);

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Promo Cards</h2>
        <span className={css.count}>{filtered.length} cards</span>
      </div>

      <div className={css.filterRow}>
        <input
          className={css.searchInput}
          type="text"
          placeholder="Search promos…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className={css.yearSelect}
          value={yearFilter}
          onChange={e => setYearFilter(e.target.value)}
        >
          <option value="all">All Years</option>
          {years.map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      <div className={css.grid}>
        {filtered.map(promo => (
          <PromoCard key={promo.id} promo={promo} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--t-4)' }}>
          No promo cards found matching your filters.
        </div>
      )}
    </div>
  );
}
