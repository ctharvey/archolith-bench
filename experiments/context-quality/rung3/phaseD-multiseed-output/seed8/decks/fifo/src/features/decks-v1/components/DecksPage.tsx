import { useState, useMemo } from 'react';
import type { DeckV1 } from '../types';
import DeckGrid from './DeckGrid';
import DeckFilter from './DeckFilter';

interface DecksPageProps {
  decks: DeckV1[];
  totalDecks: number;
  totalValue: number;
}

export default function DecksPage({ decks, totalDecks, totalValue }: DecksPageProps) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('value');
  const [format, setFormat] = useState('all');

  const filtered = useMemo(() => {
    let result = [...decks];

    // Filter by format
    if (format !== 'all') {
      result = result.filter(d => d.format === format);
    }

    // Filter by search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        d =>
          d.name.toLowerCase().includes(q) ||
          d.archetype.toLowerCase().includes(q) ||
          d.format.toLowerCase().includes(q)
      );
    }

    // Sort
    if (sort === 'value') {
      result.sort((a, b) => b.totalValue - a.totalValue);
    } else if (sort === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sort === 'cards') {
      result.sort((a, b) => b.cardCount - a.cardCount);
    } else if (sort === 'updated') {
      result.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    }

    return result;
  }, [decks, search, sort, format]);

  const filteredTotalValue = filtered.reduce((sum, d) => sum + d.totalValue, 0);

  return (
    <div>
      <DeckFilter
        totalDecks={filtered.length}
        search={search}
        sort={sort}
        format={format}
        onSearchChange={setSearch}
        onSortChange={setSort}
        onFormatChange={setFormat}
      />
      <DeckGrid
        decks={filtered}
        totalDecks={filtered.length}
        totalValue={filteredTotalValue}
      />
    </div>
  );
}
