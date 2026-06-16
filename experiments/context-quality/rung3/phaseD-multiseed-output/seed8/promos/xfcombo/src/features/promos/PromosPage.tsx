import { useState, useMemo } from 'react';
import { PageMain } from '@/ui';
import { usePromosData } from './usePromosData';
import PromosFilterBar from './components/PromosFilterBar';
import PromosBody from './components/PromosBody';
import s from './PromosPage.module.css';

export default function PromosPage() {
  const { promos, loading, error } = usePromosData();
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('year');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    let r = promos;
    if (filter === 'recent') {
      const currentYear = new Date().getFullYear();
      r = r.filter(p => p.releaseYear >= currentYear - 2);
    } else if (filter === 'classic') {
      r = r.filter(p => p.releaseYear < 2010);
    }
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.code.toLowerCase().includes(q) ||
        p.serie.toLowerCase().includes(q),
      );
    }
    r = [...r].sort((a, b) => {
      if (sort === 'year') return b.releaseYear - a.releaseYear;
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'cards') return b.cardCount - a.cardCount;
      return 0;
    });
    return r;
  }, [promos, filter, sort, search]);

  if (loading) {
    return (
      <PageMain>
        <div className="page">
          <div className="page-head">
            <h1 className="page-title">P<em>romos</em></h1>
            <div className="page-meta mono xs muted">loading…</div>
          </div>
        </div>
      </PageMain>
    );
  }

  if (error) {
    return (
      <PageMain>
        <div className="page">
          <div className="page-head">
            <h1 className="page-title">P<em>romos</em></h1>
          </div>
          <div className={s.errorState}>{error}</div>
        </div>
      </PageMain>
    );
  }

  return (
    <PageMain>
      <div className="page">
        <div className="page-head">
          <div>
            <h1 className="page-title">P<em>romos</em></h1>
            <div className={`page-meta ${s.pageMetaMargin}`}>
              <b>{promos.length}</b> promo sets tracked
            </div>
          </div>
        </div>

        <PromosFilterBar
          totalPromos={promos.length}
          recentCount={promos.filter(p => p.releaseYear >= new Date().getFullYear() - 2).length}
          classicCount={promos.filter(p => p.releaseYear < 2010).length}
          filter={filter}
          sort={sort}
          search={search}
          onFilterChange={setFilter}
          onSortChange={setSort}
          onSearchChange={setSearch}
        />

        <div className="fade-in">
          <PromosBody promos={filtered} />
        </div>
      </div>
    </PageMain>
  );
}
