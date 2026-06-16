import { useState, useMemo } from 'react';
import { PageMain } from '@/ui';
import { usePromosData } from './usePromosData';
import PromosFilterBar from './components/PromosFilterBar';
import PromosGrid from './components/PromosGrid';
import s from './PromosPage.module.css';

export default function PromosPage() {
  const { promos, loading, error } = usePromosData();
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('year');
  const [yearFilter, setYearFilter] = useState<string>('all');

  const years = useMemo(() => {
    const y = new Set<string>();
    promos.forEach(p => {
      if (p.releaseYear) y.add(p.releaseYear);
    });
    return Array.from(y).sort((a, b) => parseInt(b) - parseInt(a));
  }, [promos]);

  const filtered = useMemo(() => {
    let r = promos;
    if (yearFilter !== 'all') {
      r = r.filter(p => p.releaseYear === yearFilter);
    }
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.setName?.toLowerCase().includes(q) ||
        p.number?.toLowerCase().includes(q)
      );
    }
    r = [...r].sort((a, b) => {
      if (sort === 'year') return (b.releaseYear || '').localeCompare(a.releaseYear || '');
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'price') return (b.marketPrice || 0) - (a.marketPrice || 0);
      return 0;
    });
    return r;
  }, [promos, search, sort, yearFilter]);

  if (loading) {
    return (
      <PageMain>
        <div className="page">
          <div className="page-head">
            <h1 className="page-title">Pr<em>omos</em></h1>
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
            <h1 className="page-title">Pr<em>omos</em></h1>
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
            <h1 className="page-title">Pr<em>omos</em></h1>
            <div className={`page-meta ${s.pageMetaMargin}`}>
              <b>{promos.length}</b> promo cards tracked
            </div>
          </div>
        </div>

        <PromosFilterBar
          total={promos.length}
          search={search}
          sort={sort}
          yearFilter={yearFilter}
          years={years}
          onSearchChange={setSearch}
          onSortChange={setSort}
          onYearFilterChange={setYearFilter}
        />

        <div className="fade-in">
          <PromosGrid promos={filtered} />
        </div>
      </div>
    </PageMain>
  );
}
