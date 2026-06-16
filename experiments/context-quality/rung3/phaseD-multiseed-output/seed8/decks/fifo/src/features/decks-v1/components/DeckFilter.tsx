import s from './DeckFilter.module.css';

interface DeckFilterProps {
  totalDecks: number;
  search: string;
  sort: string;
  format: string;
  onSearchChange: (q: string) => void;
  onSortChange: (s: string) => void;
  onFormatChange: (f: string) => void;
}

export default function DeckFilter({
  totalDecks,
  search,
  sort,
  format,
  onSearchChange,
  onSortChange,
  onFormatChange,
}: DeckFilterProps) {
  return (
    <div className={`box ${s.filterBar}`}>
      <div className={`row ${s.filterGroup}`}>
        <span style={{ fontSize: 12, color: 'var(--t-4)' }}>
          {totalDecks} decks
        </span>
        <select
          value={format}
          onChange={e => onFormatChange(e.target.value)}
          className="sets-sort-select"
        >
          <option value="all">all formats</option>
          <option value="Standard">Standard</option>
          <option value="Expanded">Expanded</option>
          <option value="Legacy">Legacy</option>
        </select>
      </div>
      <div className={`row ${s.sortGroup}`}>
        <input
          placeholder="Search decks…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="sets-search-input"
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className="sets-sort-select"
        >
          <option value="value">sort: total value</option>
          <option value="name">sort: name</option>
          <option value="cards">sort: card count</option>
          <option value="updated">sort: updated</option>
        </select>
      </div>
    </div>
  );
}
