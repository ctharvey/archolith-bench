import type { DeckDto, DeckDisplay } from './types';
import { formatUSD, formatDate } from '@/domain/formatters';

/** Map a DeckDto to DeckDisplay */
export function toDeckDisplay(dto: DeckDto): DeckDisplay {
  return {
    id: dto.id,
    name: dto.name,
    format: dto.format,
    totalValue: dto.totalValue,
    totalValueFormatted: formatUSD(dto.totalValue, { locale: true }),
    cardCount: dto.cardCount,
    updatedAt: dto.updatedAt,
    updatedAtFormatted: formatDate(dto.updatedAt),
  };
}

/** Map an array of DeckDto to DeckDisplay */
export function toDeckDisplayList(dtos: DeckDto[]): DeckDisplay[] {
  return dtos.map(toDeckDisplay);
}
