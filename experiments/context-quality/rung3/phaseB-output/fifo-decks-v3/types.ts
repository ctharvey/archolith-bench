/** A deck as rendered by Decks v3 components */
export interface DeckItem {
  id: string;
  name: string;
  format: string;
  cardCount: number;
  totalValue: number;
  displayValue: string;
  d7Pct: string;
  d7Num: number;
  d7Dir: 'up' | 'dn' | 'flat';
  sym: string;
  color: string;
  topCardImages: (string | null)[];
  topCardIds: string[];
  setNames: string[];
}
