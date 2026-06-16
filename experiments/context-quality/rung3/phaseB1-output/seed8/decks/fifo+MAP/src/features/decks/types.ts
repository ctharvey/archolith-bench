export interface Deck {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  uniqueCards: number;
  topCardName: string;
  topCardValue: number;
  topCardImageUrl: string | null;
  color: string;
  lastUpdated: string;
}

export interface DecksBrowseData {
  decks: Deck[];
  totalDecks: number;
  totalValue: number;
}
