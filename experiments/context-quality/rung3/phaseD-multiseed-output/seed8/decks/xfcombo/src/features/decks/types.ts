export interface DeckBrowseItem {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  updatedAt: string;
}

export interface DecksPageData {
  decks: DeckBrowseItem[];
  totalValue: number;
  totalDecks: number;
}
