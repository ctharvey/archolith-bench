import { PageMain } from '@/ui';
import { useDecksData } from './useDecksData';
import { Kpi } from '@/ui/data-display';
import DeckTile from './components/DeckTile';
import s from './DecksPage.module.css';

const SORT_OPTIONS = [
  { value: 'value', label: 'Total Value' },
  { value: 'avg', label: 'Avg Card' },
  { value: 'cards', label: 'Card Count' },
  { value: 'name', label: 'Name' },
  { value: 'delta', label: 'Δ 7d' },
];

export default function DecksPage() {
  const { decks, stats, loading, error, search, setSearch, sort, setSort } = useDecksData();

  if (loading) {
    return (
      <div className="decks"><PageMain><div className="page">
        <h1 className="page-title">D<em>ecks</em></h1>
        <div className="page-meta mono xs muted">loading…</div>
      </div></PageMain></div>
    );
  }

  if (error) {
    return (
      <div className="decks"><PageMain><div className="page">
        <h1 className="page-title">D<em>ecks</em></h1>
        <div className={s.errorMsg}>{error}</div>
      </div></PageMain></div>
    );
  }

  return (
    <div className="decks">
      <PageMain>
        <div className="page">

          <div className="page-head">
            <h1 className="page-title">D<em>ecks</em></h1>
            <div className={`page-meta ${s.pageMeta}`}>
              <b>{stats.totalDecks}</b> set collections
            </div>
          </div>

          <div className={`grid-4 ${s.kpiGrid}`}>
            <Kpi label="Set Decks" value={stats.totalDecks} sub={stats.biggestDeck ? `biggest: ${stats.biggestDeck}` : undefined} />
            <Kpi label="Total Market Value" value={`$${stats.totalMarketValue >= 1_000_000 ? (stats.totalMarketValue / 1_000_000).toFixed(1) + 'M' : (stats.totalMarketValue / 1_000).toFixed(1) + 'K'}`} sub="across all sets" />
            <Kpi label="Avg Deck Value" value={stats.avgDeckValue >= 1000 ? `$${(stats.avgDeckValue / 1000).toFixed(1)}K` : `$${stats.avgDeckValue.toFixed(0)}`} sub="per set" />
            <Kpi label="Biggest" value={stats.biggestDeck ?? '—'} sub="by total value" />
          </div>

          <div className={`box ${s.filterBar}`}>
            <div className={`row ${s.searchSort}`}>
              <input placeholder="Search decks, series…" value={search} onChange={e => setSearch(e.target.value)} className="decks-search-input" />
              <select value={sort} onChange={e => setSort(e.target.value)} className="decks-sort-select">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>

          <div className="deck-grid">
            {decks.map(d => <DeckTile key={d.setId} deck={d} />)}
          </div>

        </div>
      </PageMain>
    </div>
  );
}
