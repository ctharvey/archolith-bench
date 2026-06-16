export interface DeckData {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  uniqueCards: number;
  topCardName: string;
  topCardValue: number;
  lastUpdated: string;
}

export interface DecksPageData {
  decks: DeckData[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
