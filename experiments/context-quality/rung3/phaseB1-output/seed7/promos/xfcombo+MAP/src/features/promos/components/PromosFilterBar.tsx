import { SearchInput, Select } from '@/ui/controls';

interface PromosFilterBarProps {
  total: number;
  years: number[];
  yearFilter: string;
  search: string;
  sort: string;
  onYearFilterChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onSortChange: (value: string) => void;
}

export default function PromosFilterBar({
  total,
  years,
  yearFilter,
  search,
  sort,
  onYearFilterChange,
  onSearchChange,
  onSortChange,
}: PromosFilterBarProps) {
  return (
    <div className="filter-bar">
      <div className="filter-bar__left">
        <SearchInput
          value={search}
          onChange={onSearchChange}
          placeholder="Search promos…"
        />
      </div>
      <div className="filter-bar__right">
        <Select
          value={yearFilter}
          onChange={e => onYearFilterChange(e.target.value)}
          aria-label="Filter by year"
        >
          <option value="all">All Years</option>
          {years.map(y => (
            <option key={y} value={String(y)}>{y}</option>
          ))}
        </Select>
        <Select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          aria-label="Sort by"
        >
          <option value="year">Year</option>
          <option value="name">Name</option>
          <option value="fmv">Market Price</option>
        </Select>
        <span className="mono xs muted">{total} promos</span>
      </div>
    </div>
  );
}
