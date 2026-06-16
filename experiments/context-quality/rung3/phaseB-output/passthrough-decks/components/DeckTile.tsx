import type { DeckItem } from '../types';
import { setUrl } from '@/domain/slug';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: DeckItem;
}

export default function DeckTile({ deck }: DeckTileProps) {
  return (
    <a className="deck-tile clickable-link" href={setUrl(deck.setId, deck.setName)}>
      <div className={s.deckHeader} style={{ borderLeftColor: deck.color }}>
        <div className={s.deckName}>{deck.setName}</div>
        {deck.serieName && <div className="mono xs muted">{deck.serieName}</div>}
      </div>
      <div className={s.deckBody}>
        <div className={s.deckStats}>
          <div className={s.stat}>
            <span className={s.statLabel}>Value</span>
            <span className={`mono ${s.statValue}`}>{deck.totalValueStr}</span>
          </div>
          <div className={s.stat}>
            <span className={s.statLabel}>Cards</span>
            <span className={`mono ${s.statValue}`}>{deck.cardCount}</span>
          </div>
          <div className={s.stat}>
            <span className={s.statLabel}>Avg</span>
            <span className={`mono ${s.statValue}`}>{deck.avgValueStr}</span>
          </div>
        </div>
        {deck.delta7d != null && (
          <div className={`mono xs ${deck.delta7d > 0 ? 'up' : 'down'} ${s.deckDelta}`}>
            {deck.delta7dStr} (7d)
          </div>
        )}
      </div>
    </a>
  );
}
