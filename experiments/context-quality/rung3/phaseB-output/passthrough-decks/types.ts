import type { DeltaDirection } from '@/domain/models';

export interface DeckItem {
  setId: string;
  setName: string;
  serieName: string | null;
  cardCount: number;
  avgFmv: number | null;
  totalValue: number | null;
  totalValueStr: string;
  avgValueStr: string;
  delta7d: number | null;
  delta7dStr: string;
  delta7dDir: DeltaDirection;
  topCardId: string | null;
  releaseDate: string | null;
  color: string;
}
