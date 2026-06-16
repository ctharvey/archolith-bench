import s from './DeckFilterBar.module.css';

interface DeckFilterBarProps {
  totalDecks: number;
  filter: string;
  sort: string;
  search: string;
  onFilterChange: (f: string) => void;
  onSortChange: (s: string) => void;
  onSearchChange: (q: string) => void;
}

export default function DeckFilterBar({
  totalDecks,
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
        <button
          className={`pill ${filter === 'all' ? 'active' : ''}`}
          onClick={() => onFilterChange('all')}
        >
          All ({totalDecks})
        </button>
        <button
          className={`pill ${filter === 'standard' ? 'active' : ''}`}
          onClick={() => onFilterChange('standard')}
        >
          Standard
        </button>
        <button
          className={`pill ${filter === 'expanded' ? 'active' : ''}`}
          onClick={() => onFilterChange('expanded')}
        >
          Expanded
        </button>
      </div>
      <div className={`row ${s.sortGroup}`}>
        <input
          placeholder="Search decks, archetypes…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="decks-search-input"
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className="decks-sort-select"
        >
          <option value="value">sort: total value</option>
          <option value="cards">sort: card count</option>
          <option value="name">sort: name</option>
          <option value="updated">sort: updated</option>
        </select>
      </div>
    </div>
  );
}
