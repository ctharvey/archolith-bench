import { Select } from '@/components/Select';

interface YearFilterProps {
  years: number[];
  selectedYear?: number;
  onYearChange: (year: number | undefined) => void;
}

export function YearFilter({ years, selectedYear, onYearChange }: YearFilterProps) {
  if (years.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="year-filter" className="text-sm font-medium text-gray-700">
        Release Year:
      </label>
      <Select
        id="year-filter"
        value={selectedYear ?? ''}
        onChange={(e) => {
          const val = e.target.value;
          onYearChange(val ? Number(val) : undefined);
        }}
      >
        <option value="">All Years</option>
        {years.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </Select>
    </div>
  );
}
