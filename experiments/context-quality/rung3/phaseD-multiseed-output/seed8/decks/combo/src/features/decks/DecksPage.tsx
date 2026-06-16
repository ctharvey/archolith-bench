import { PageMain } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';
import { useDecksData } from './useDecksData';
import { Kpi } from '@/ui/data-display';
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

  const { decks, totalDecks, totalValue } = data;

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
          <div className={s.kpiGrid} style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
            <Kpi label="Total Decks" value={totalDecks} sub={`${decks.length} loaded`} />
            <Kpi label="Total Value" value={formatUSDshort(totalValue)} sub="market value" />
          </div>

          {/* Deck list */}
          <div className={s.deckGrid}>
            {decks.map((deck) => (
              <div key={deck.id} className={s.deckTile}>
                <div className={s.deckName}>{deck.name}</div>
                <div className={s.deckMeta}>
                  <span className={s.deckFormat}>{deck.format}</span>
                  <span className={s.deckValue}>{formatUSDshort(deck.totalValue)}</span>
                </div>
                <div className={s.deckMeta}>
                  <span className="mono xs muted">{deck.cardCount} cards</span>
                  <span className="mono xs muted">{new Date(deck.updatedAt).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </PageMain>
    </div>
  );
}
