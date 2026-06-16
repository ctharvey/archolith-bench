import { PageMain } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';
import { useDecksData } from './useDecksData';
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

  const { decks, totalValue, totalDecks } = data;

  return (
    <div className="decks">
      <PageMain>
        <div className="page">
          {/* Header */}
          <div className="page-head">
            <h1 className="page-title">D<em>ecks</em></h1>
            <div className={`page-meta ${s.pageMeta}`}>
              <b>{totalDecks}</b> decks · <b>{formatUSDshort(totalValue)}</b> total market value
            </div>
          </div>

          {/* Deck grid */}
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
