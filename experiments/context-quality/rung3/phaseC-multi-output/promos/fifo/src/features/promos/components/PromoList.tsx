import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoList.module.css';

interface PromoListProps {
  promos: PromoCard[];
}

export default function PromoList({ promos }: PromoListProps) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return promos;
    const q = search.toLowerCase();
    return promos.filter(p => 
      p.name.toLowerCase().includes(q) ||
      p.set.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q)
    );
  }, [promos, search]);

  // Sort by year descending, then by name
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      if (b.year !== a.year) return b.year - a.year;
      return a.name.localeCompare(b.name);
    });
  }, [filtered]);

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h2 className={css.title}>Promos</h2>
        <span className={css.count}>{sorted.length} cards</span>
      </div>

      <div style={{ marginBottom: 14 }}>
        <input
          placeholder="Search promos…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="sets-search-input"
          style={{ width: '100%' }}
        />
      </div>

      {sorted.length === 0 ? (
        <div className={css.empty}>
          {search ? 'No promos match your search.' : 'No promo cards found.'}
        </div>
      ) : (
        <div className={css.list}>
          {sorted.map(promo => (
            <PromoCard key={promo.id} promo={promo} />
          ))}
        </div>
      )}
    </div>
  );
}
