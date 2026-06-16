import s from './PromoFilterBar.module.css';

interface PromoFilterBarProps {
  total: number;
  search: string;
  sort: string;
  yearFilter: string;
  years: string[];
  onSearchChange: (v: string) => void;
  onSortChange: (v: string) => void;
  onYearFilterChange: (v: string) => void;
}

export default function PromoFilterBar({
  total,
  search,
  sort,
  yearFilter,
  years,
  onSearchChange,
  onSortChange,
  onYearFilterChange,
}: PromoFilterBarProps) {
  return (
    <div className={s.bar}>
      <div className={s.searchWrap}>
        <input
          type="text"
          placeholder="Search promos…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className={s.searchInput}
        />
      </div>

      <div className={s.controls}>
        <select
          value={yearFilter}
          onChange={e => onYearFilterChange(e.target.value)}
          className={s.select}
        >
          <option value="all">All years</option>
          {years.map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className={s.select}
        >
          <option value="released">Release year</option>
          <option value="name">Name</option>
          <option value="fmv">Market price</option>
        </select>

        <span className={s.count}>{total} promos</span>
      </div>
    </div>
  );
}
