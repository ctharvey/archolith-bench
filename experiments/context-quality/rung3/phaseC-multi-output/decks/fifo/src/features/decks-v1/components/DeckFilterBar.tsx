import s from './DeckFilterBar.module.css';

interface DeckFilterBarProps {
  totalDecks: number;
  search: string;
  sort: string;
  onSearchChange: (q: string) => void;
  onSortChange: (s: string) => void;
}

export default function DeckFilterBar({
  totalDecks,
  search,
  sort,
  onSearchChange,
  onSortChange,
}: DeckFilterBarProps) {
  return (
    <div className={`box ${s.filterBar}`}>
      <div className={`row ${s.filterGroup}`}>
        <span style={{ fontSize: 12, color: 'var(--t-4)' }}>
          {totalDecks} decks
        </span>
      </div>
      <div className={`row ${s.sortGroup}`}>
        <input
          placeholder="Search decks, formats, archetypes…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="decks-search-input"
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className="decks-sort-select"
        >
          <option value="updated">sort: recently updated</option>
          <option value="value">sort: total value</option>
          <option value="cards">sort: card count</option>
          <option value="name">sort: name</option>
        </select>
      </div>
    </div>
  );
}
