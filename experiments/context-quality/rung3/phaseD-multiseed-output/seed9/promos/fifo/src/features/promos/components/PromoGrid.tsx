import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCardComponent from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  promos: PromoCard[];
}

export default function PromoGrid({ promos }: PromoGridProps) {
  const [sort, setSort] = useState<'year' | 'name'>('year');
  const [search, setSearch] = useState('');

  const sorted = useMemo(() => {
    let filtered = promos;
    
    if (search.trim()) {
      const q = search.toLowerCase();
      filtered = promos.filter(p => 
        p.name.toLowerCase().includes(q) ||
        p.set.toLowerCase().includes(q) ||
        p.id.toLowerCase().includes(q)
      );
    }

    return [...filtered].sort((a, b) => {
      if (sort === 'year') return b.year - a.year;
      return a.name.localeCompare(b.name);
    });
  }, [promos, sort, search]);

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h1 className={css.title}>Promos</h1>
        <span className={css.count}>{sorted.length} cards</span>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <input
          placeholder="Search promos…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-2)',
            color: 'var(--t-1)',
            fontSize: 13,
            flex: 1,
            maxWidth: 300,
          }}
        />
        <select
          value={sort}
          onChange={e => setSort(e.target.value as 'year' | 'name')}
          style={{
            padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-2)',
            color: 'var(--t-1)',
            fontSize: 13,
          }}
        >
          <option value="year">Sort: Year</option>
          <option value="name">Sort: Name</option>
        </select>
      </div>

      <div className={css.grid}>
        {sorted.length > 0 ? (
          sorted.map(promo => (
            <PromoCardComponent key={promo.id} promo={promo} />
          ))
        ) : (
          <div className={css.empty}>
            {search ? 'No promos match your search' : 'No promos available'}
          </div>
        )}
      </div>
    </div>
  );
}
