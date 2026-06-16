import styles from './BundleFilterBar.module.css';

interface BundleFilterBarProps {
  totalBundles: number;
  activeCount: number;
  filter: string;
  sort: string;
  search: string;
  onFilterChange: (f: string) => void;
  onSortChange: (s: string) => void;
  onSearchChange: (q: string) => void;
}

export default function BundleFilterBar({
  totalBundles,
  activeCount,
  filter,
  sort,
  search,
  onFilterChange,
  onSortChange,
  onSearchChange,
}: BundleFilterBarProps) {
  return (
    <div className={`box ${styles.filterBar}`}>
      <div className={styles.filterGroup}>
        <button
          className={`pill ${filter === 'all' ? 'active' : ''}`}
          onClick={() => onFilterChange('all')}
        >
          All ({totalBundles})
        </button>
        <button
          className={`pill ${filter === 'active' ? 'active' : ''}`}
          onClick={() => onFilterChange('active')}
        >
          Active ({activeCount})
        </button>
      </div>
      <div className={styles.sortGroup}>
        <input
          placeholder="Search bundles…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="bundle-search-input"
        />
        <select
          value={sort}
          onChange={e => onSortChange(e.target.value)}
          className="bundle-sort-select"
        >
          <option value="discount">sort: discount %</option>
          <option value="price">sort: price</option>
          <option value="name">sort: name</option>
          <option value="items">sort: item count</option>
        </select>
      </div>
    </div>
  );
}
