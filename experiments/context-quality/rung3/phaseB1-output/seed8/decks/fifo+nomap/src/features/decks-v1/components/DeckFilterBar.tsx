import s from './DeckFilterBar.module.css';

interface DeckFilterBarProps {
  totalDecks: number;
  totalMarketValue: string;
  filter: string;
  sort: string;
  search: string;
  onFilterChange: (f: string) => void;
  onSortChange: (s: string) => void;
  onSearchChange: (q: string) => void;
}

export default function DeckFilterBar({
  totalDecks,
  totalMarketValue,
  filter,
  sort,
  search,
  onFilterChange,
  onSortChange,
  onSearchChange,
}: DeckFilterBarProps) {
  return (
    <div className={`box ${s.filterBar}`}>
      <div className={`row ${s.filterGroup}`}>
        <span style={{ fontSize: 12, color: 'var(--t-4)' }}>
          {totalDecks} decks · {totalMarketValue} total
        </span>
      </div>
      <div className={`row ${s.sortGroup}`}>
        <input
          placeholder="Search decks…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className={s.searchInput}
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
        >
          <option value="value">sort: total value</option>
          <option value="cards">sort: card count</option>
          <option value="name">sort: name</option>
          <option value="updated">sort: last updated</option>
        </select>
      </div>
    </div>
  );
}
