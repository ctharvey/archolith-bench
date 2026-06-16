/** A deck as returned by the API */
export interface DeckDto {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  updatedAt: string;
  createdAt: string;
}

/** A deck as rendered by the browse components */
export interface DeckDisplay {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  updatedAt: string;
  updatedAtFormatted: string;
}
