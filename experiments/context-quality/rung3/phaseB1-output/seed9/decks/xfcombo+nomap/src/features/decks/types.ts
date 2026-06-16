export interface DeckData {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  topCards: DeckCard[];
  updatedAt: string;
}

export interface DeckCard {
  name: string;
  price: number;
  quantity: number;
}

export interface DecksPageData {
  decks: DeckData[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
