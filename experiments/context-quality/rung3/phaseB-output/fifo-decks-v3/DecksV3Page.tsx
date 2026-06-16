import { PageMain } from '@/ui';
import { Kpi } from '@/ui/data-display';
import { formatUSD } from '@/domain/formatters';
import { useDecksV3Data } from './useDecksV3Data';
import DeckTile from './components/DeckTile';
import s from './DecksV3Page.module.css';

const SORT_OPTIONS = [
  { value: 'value', label: 'Value' },
  { value: 'delta', label: 'Δ 7d' },
  { value: 'cards', label: 'Cards' },
  { value: 'name', label: 'Name' },
];

export default function DecksV3Page() {
  const { decks, hotDecks, totalDecks, totalValue, countUp, countDn, countFlat, loading, error, filter, setFilter, sort, setSort, search, setSearch } = useDecksV3Data();

  if (loading) {
    return (
      <div className="decks-v3">
        <PageMain><div className="page">
          <h1 className="page-title">D<em>ecks</em></h1>
          <div className="kpis" style={{ marginBottom: 18 }}>
            <div className="kpi"><span className="k-label">Loading…</span></div>
          </div>
          <div className="card-grid">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 180, borderRadius: 12 }} />
            ))}
          </div>
        </div></PageMain>
      </div>
    );
  }

  if (error) {
    return (
      <div className="decks-v3">
        <PageMain><div className="page">
          <h1 className="page-title">D<em>ecks</em></h1>
          <p className={s.errorMsg}>{error}</p>
        </div></PageMain>
      </div>
    );
  }

  return (
    <div className="decks-v3">
      <PageMain>
        <div className="page">

          <h1 className="page-title">D<em>ecks</em></h1>
          <div className={`mono muted ${s.pageMeta}`}>{totalDecks} decks &middot; {formatUSD(totalValue, { locale: true })} total value</div>

          {/* KPI strip */}
          <div className={`kpis ${s.kpiGrid}`}>
            <Kpi label="Decks" value={totalDecks} />
            <Kpi label="Total value" value={formatUSD(totalValue, { locale: true })} />
            <Kpi label="Rising" value={countUp} delta={`+${countUp}`} deltaDir="up" />
            <Kpi label="Falling" value={countDn} delta={`-${countDn}`} deltaDir="down" />
          </div>

          {/* Hot decks */}
          {hotDecks.length > 0 && (
            <>
              <div className="label decks-section-label">Top movers</div>
              <div className="hot-strip-decks" style={{ display: 'flex', gap: 10, marginBottom: 20, overflowX: 'auto' }}>
                {hotDecks.map(d => (
                  <DeckTile key={d.id} deck={d} compact />
                ))}
              </div>
            </>
          )}

          {/* Filter / sort / search */}
          <div className={`box ${s.filterBar}`}>
            <div className={`row ${s.filterPills}`}>
              <span className={`pill${filter !== 'all' ? ' dim' : ''} ${s.filterPill}`} onClick={() => setFilter('all')}>All ({totalDecks})</span>
              <span className={`pill up${filter !== 'up' ? ' dim' : ''} ${s.filterPill}`} onClick={() => setFilter('up')}>Up ↑ ({countUp})</span>
              <span className={`pill${filter !== 'flat' ? ' dim' : ''} ${s.filterPill}`} onClick={() => setFilter('flat')}>Flat ({countFlat})</span>
              <span className={`pill down${filter !== 'dn' ? ' dim' : ''} ${s.filterPill}`} onClick={() => setFilter('dn')}>Down ↓ ({countDn})</span>
            </div>
            <div className={`row ${s.searchSort}`}>
              <input placeholder="Search decks, sets…" value={search} onChange={e => setSearch(e.target.value)} className="cards-search-input" />
              <select value={sort} onChange={e => setSort(e.target.value)} className="cards-sort-select">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>

          {/* Deck grid */}
          <div className="card-grid">
            {decks.map(d => <DeckTile key={d.id} deck={d} />)}
          </div>

        </div>
      </PageMain>
    </div>
  );
}
