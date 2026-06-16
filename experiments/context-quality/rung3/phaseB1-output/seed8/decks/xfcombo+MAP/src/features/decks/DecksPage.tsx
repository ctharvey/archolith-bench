import { PageMain } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';
import { useDecksData } from './useDecksData';
import { Kpi } from '@/ui/data-display';
import DeckTile from './components/DeckTile';
import s from './DecksPage.module.css';

export default function DecksPage() {
  const { data, loading, error } = useDecksData();

  if (loading) {
    return (
      <div className="decks">
        <PageMain>
          <div className="page">
            <h1 className="page-title">D<em>ecks</em></h1>
            <div className="page-meta mono xs muted">loading…</div>
          </div>
        </PageMain>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="decks">
        <PageMain>
          <div className="page">
            <h1 className="page-title">D<em>ecks</em></h1>
            <div className={s.errorMsg}>{error || 'No data'}</div>
          </div>
        </PageMain>
      </div>
    );
  }

  const { decks, totalDecks, totalValue, avgValue } = data;

  return (
    <div className="decks">
      <PageMain>
        <div className="page">
          {/* Header */}
          <div className="page-head">
            <h1 className="page-title">D<em>ecks</em></h1>
            <div className={`page-meta ${s.pageMeta}`}>
              <b>{totalDecks}</b> decks · <b>{formatUSDshort(totalValue)}</b> total value · <b>{formatUSDshort(avgValue)}</b> avg
            </div>
          </div>

          {/* KPI strip */}
          <div className={s.kpiGrid}>
            <Kpi label="Total Decks" value={totalDecks} sub={formatUSDshort(totalValue)} />
            <Kpi label="Average Value" value={formatUSDshort(avgValue)} sub={`${decks.length} decks`} />
          </div>

          {/* Deck list */}
          <div className={`label ${s.deckListLabel}`}>All Decks</div>
          <div className={s.deckGrid}>
            {decks.map(deck => (
              <DeckTile key={deck.id} deck={deck} />
            ))}
          </div>
        </div>
      </PageMain>
    </div>
  );
}
