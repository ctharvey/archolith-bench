import { PageMain } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';
import { useDecksData } from './useDecksData';
import { Kpi } from '@/ui/data-display';
import s from './DecksPage.module.css';

export default function DecksPage() {
  const { data, loading, error } = useDecksData();

  if (loading) {
    return (
      <div className="decks-page">
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
      <div className="decks-page">
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
    <div className="decks-page">
      <PageMain>
        <div className="page">
          {/* Header */}
          <div className="page-head">
            <h1 className="page-title">Decks</h1>
            <div className={`page-meta ${s.pageMeta}`}>
              <b>{totalDecks}</b> decks · <b>{formatUSDshort(totalValue)}</b> total value · avg <b>{formatUSDshort(avgDeckValue)}</b>
            </div>
          </div>

          {/* KPI strip */}
          <div className={s.kpiGrid} style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <Kpi label="Total Decks" value={totalDecks} />
            <Kpi label="Total Value" value={formatUSDshort(totalValue)} />
            <Kpi label="Avg Deck Value" value={formatUSDshort(avgDeckValue)} />
          </div>

          {/* Deck grid */}
          <div className={`label`}>All Decks</div>
          <div className={s.deckGrid}>
            {decks.map((deck) => (
              <div key={deck.id} className={s.deckTile}>
                <div className={s.deckName}>{deck.name}</div>
                <div className={s.deckFormat} style={{ color: deck.color }}>{deck.format}</div>
                <div className={s.deckValue}>{formatUSDshort(deck.totalValue)}</div>
                <div className={s.deckStats}>
                  <span>{deck.cardCount} cards</span>
                  <span>{deck.uniqueCards} unique</span>
                </div>
                <div className={s.deckMeta}>
                  <span>Updated: {deck.lastUpdated ? new Date(deck.lastUpdated).toLocaleDateString() : '—'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </PageMain>
    </div>
  );
}
