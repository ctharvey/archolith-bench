import s from './PromosFilterBar.module.css';

interface PromosFilterBarProps {
  totalPromos: number;
  recentCount: number;
  classicCount: number;
  filter: string;
  sort: string;
  search: string;
  onFilterChange: (filter: string) => void;
  onSortChange: (sort: string) => void;
  onSearchChange: (search: string) => void;
}

export default function PromosFilterBar({
  totalPromos,
  recentCount,
  classicCount,
  filter,
  sort,
  search,
  onFilterChange,
  onSortChange,
  onSearchChange,
}: PromosFilterBarProps) {
  return (
    <div className={s.bar}>
      <div className={s.filters}>
        <button
          className={`${s.filterBtn} ${filter === 'all' ? s.active : ''}`}
          onClick={() => onFilterChange('all')}
        >
          All <span className={s.count}>{totalPromos}</span>
        </button>
        <button
          className={`${s.filterBtn} ${filter === 'recent' ? s.active : ''}`}
          onClick={() => onFilterChange('recent')}
        >
          Recent <span className={s.count}>{recentCount}</span>
        </button>
        <button
          className={`${s.filterBtn} ${filter === 'classic' ? s.active : ''}`}
          onClick={() => onFilterChange('classic')}
        >
          Classic <span className={s.count}>{classicCount}</span>
        </button>
      </div>

      <div className={s.controls}>
        <input
          type="text"
          placeholder="Search promos…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className={s.searchInput}
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className={s.sortSelect}
        >
          <option value="year">Year</option>
          <option value="name">Name</option>
          <option value="cards">Card Count</option>
        </select>
      </div>
    </div>
  );
}
