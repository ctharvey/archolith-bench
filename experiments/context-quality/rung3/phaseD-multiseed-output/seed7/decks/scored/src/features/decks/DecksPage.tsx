import { PageMain } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';
import { useDecksData } from './useDecksData';
import { Kpi } from '@/ui/data-display';
import DeckCard from './components/DeckCard';
import s from './DecksPage.module.css';

export default function DecksPage() {
  const { data, loading, error } = useDecksData();

  if (loading) {
    return (
      <div className="decks">
        <PageMain>
          <div className="page">
            <h1 className="page-title">Decks</h1>
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
            <h1 className="page-title">Decks</h1>
            <div className={s.errorMsg}>{error || 'No data'}</div>
          </div>
        </PageMain>
      </div>
    );
  }

  const { decks, totalDecks, totalValue, avgDeckValue } = data;

  return (
    <div className="decks">
      <PageMain>
        <div className="page">
          {/* Header */}
          <div className="page-head">
            <h1 className="page-title">Decks</h1>
            <div className={`page-meta ${s.pageMeta}`}>
              <b>{totalDecks}</b> decks · <b>{formatUSDshort(totalValue)}</b> total value
            </div>
          </div>

          {/* KPI strip */}
          <div className={s.kpiGrid} style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <Kpi label="Total decks" value={totalDecks} />
            <Kpi label="Total value" value={formatUSDshort(totalValue)} />
            <Kpi label="Avg deck value" value={formatUSDshort(avgDeckValue)} />
          </div>

          {/* Deck list */}
          <div className={`label ${s.deckListLabel}`}>All decks</div>
          <div className={s.deckGrid}>
            {decks.map((deck) => (
              <DeckCard key={deck.id} deck={deck} />
            ))}
          </div>
        </div>
      </PageMain>
    </div>
  );
}
