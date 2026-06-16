import type { DeckItem } from '../types';
import { cardUrl } from '@/domain/slug';
import s from './DeckTile.module.css';

interface DeckTileProps {
  deck: DeckItem;
  compact?: boolean;
}

export default function DeckTile({ deck, compact }: DeckTileProps) {
  const src = deck.topCardImages[0];

  return (
    <a className={s.tile} href={`/deck/${deck.id}`} style={{ '--deck-accent': deck.color } as React.CSSProperties}>
      {src && (
        <div className={s.imgWrap}>
          <img src={src} alt="" className={s.img} loading="lazy" />
        </div>
      )}
      <div className={s.body}>
        <div className={s.nameWrap}>
          <span className={s.sym} style={{ background: deck.color }}>{deck.sym}</span>
          <span className={s.name}>{deck.name}</span>
        </div>
        <div className={`mono xs muted`}>{deck.format} &middot; {deck.cardCount} cards</div>
        <div className={s.valueRow}>
          <div>
            <div className={`mono ${s.value}`}>{deck.displayValue}</div>
            <div className={`mono xs ${deck.d7Num > 0 ? 'up' : deck.d7Num < 0 ? 'down' : 'flat'}`}>{deck.d7Pct} (7d)</div>
          </div>
        </div>
        {!compact && deck.topCardImages.length > 1 && (
          <div className={s.miniStrip}>
            {deck.topCardImages.slice(1, 4).map((url, i) =>
              url ? <img key={i} src={url} alt="" className={s.miniImg} loading="lazy" /> : null
            )}
          </div>
        )}
        {!compact && deck.setNames.length > 0 && (
          <div className={`mono xs muted ${s.sets}`}>
            {deck.setNames.slice(0, 3).join(', ')}{deck.setNames.length > 3 ? '…' : ''}
          </div>
        )}
      </div>
    </a>
  );
}
