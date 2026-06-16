import type { DecksV3Deck } from '../types';
import DeckTile from './DeckTile';
import s from './DeckGrid.module.css';

interface DeckGridProps {
  decks: DecksV3Deck[];
  totalDecks: number;
}

export default function DeckGrid({ decks, totalDecks }: DeckGridProps) {
  return (
    <div>
      <div className={s.header}>
        <h2 className={s.title}>Decks</h2>
        <span className={s.count}>{totalDecks} decks</span>
      </div>
      <div className={s.deckGrid}>
        {decks.map(deck => (
          <DeckTile key={deck.id} deck={deck} />
        ))}
      </div>
    </div>
  );
}
