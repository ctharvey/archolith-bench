/** A deck as displayed on the browse screen */
export interface DeckItem {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  updatedAt: string;
}

/** Data returned by the decks adapter */
export interface DecksPageData {
  decks: DeckItem[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
