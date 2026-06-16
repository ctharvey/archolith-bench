export interface DeckSummary {
  id: string;
  name: string;
  format: string;
  totalCards: number;
  marketValue: number;
  topCardName: string;
  topCardValue: number;
  updatedAt: string;
}

export interface DecksPageData {
  decks: DeckSummary[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
