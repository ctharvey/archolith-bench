import { useMemo } from 'react';
import type { DeckV1 } from '../types';
import DeckCard from './DeckCard';
import css from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DeckV1[];
  totalValue: number;
  search: string;
  sort: string;
}

export default function DeckGrid({ decks, totalValue, search, sort }: DeckGridProps) {
  const filtered = useMemo(() => {
    let result = decks;

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        d =>
          d.name.toLowerCase().includes(q) ||
          d.format.toLowerCase().includes(q) ||
          d.archetype.toLowerCase().includes(q)
      );
    }

    switch (sort) {
      case 'value':
        result.sort((a, b) => b.totalValue - a.totalValue);
        break;
      case 'cards':
        result.sort((a, b) => b.cardCount - a.cardCount);
        break;
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'updated':
      default:
        result.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        break;
    }

    return result;
  }, [decks, search, sort]);

  const formattedTotal = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(totalValue);

  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Decks</h2>
        <div className={css.totalValue}>
          Total market value: <span className={css.totalValueAmount}>{formattedTotal}</span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className={css.empty}>
          {search ? 'No decks match your search.' : 'No decks available.'}
        </div>
      ) : (
        <div className={css.grid}>
          {filtered.map(deck => (
            <DeckCard key={deck.id} deck={deck} />
          ))}
        </div>
      )}
    </div>
  );
}
