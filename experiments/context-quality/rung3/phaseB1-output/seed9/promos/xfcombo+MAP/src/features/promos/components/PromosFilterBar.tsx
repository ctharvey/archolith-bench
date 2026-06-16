import { SearchInput, Select } from '@/ui/controls';
import s from './PromosFilterBar.module.css';

interface PromosFilterBarProps {
  total: number;
  search: string;
  sort: string;
  yearFilter: string;
  years: string[];
  onSearchChange: (v: string) => void;
  onSortChange: (v: string) => void;
  onYearFilterChange: (v: string) => void;
}

export default function PromosFilterBar({
  total,
  search,
  sort,
  yearFilter,
  years,
  onSearchChange,
  onSortChange,
  onYearFilterChange,
}: PromosFilterBarProps) {
  return (
    <div className={s.bar}>
      <div className={s.left}>
        <SearchInput
          placeholder="Search promos…"
          value={search}
          onChange={onSearchChange}
        />
      </div>
      <div className={s.right}>
        <span className={s.count}>{total} promos</span>
        <Select value={yearFilter} onChange={e => onYearFilterChange(e.target.value)}>
          <option value="all">All years</option>
          {years.map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </Select>
        <Select value={sort} onChange={e => onSortChange(e.target.value)}>
          <option value="year">Year</option>
          <option value="name">Name</option>
          <option value="price">Price</option>
        </Select>
      </div>
    </div>
  );
}
