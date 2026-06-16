import { useState, useMemo } from 'react';
import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  promos: PromoCard[];
}

export default function PromoGrid({ promos }: PromoGridProps) {
  const [sortYear, setSortYear] = useState<'desc' | 'asc'>('desc');

  const sorted = useMemo(() => {
    const arr = [...promos];
    arr.sort((a, b) => {
      if (a.year !== b.year) {
        return sortYear === 'desc' ? b.year - a.year : a.year - b.year;
      }
      return a.name.localeCompare(b.name);
    });
    return arr;
  }, [promos, sortYear]);

  const toggleSort = () => {
    setSortYear(prev => prev === 'desc' ? 'asc' : 'desc');
  };

  return (
    <div className={css.container}>
      <div className={css.header}>
        <h2 className={css.title}>Promos</h2>
        <div className="row" style={{ gap: 10, alignItems: 'center' }}>
          <span className={css.count}>{promos.length} cards</span>
          <button
            onClick={toggleSort}
            className="sets-sort-select"
            style={{ fontSize: 11, padding: '4px 10px', cursor: 'pointer' }}
          >
            Year {sortYear === 'desc' ? '↓' : '↑'}
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className={css.empty}>No promo cards found.</div>
      ) : (
        <div className={css.grid}>
          {sorted.map(promo => (
            <PromoCard key={promo.id} promo={promo} />
          ))}
        </div>
      )}
    </div>
  );
}
