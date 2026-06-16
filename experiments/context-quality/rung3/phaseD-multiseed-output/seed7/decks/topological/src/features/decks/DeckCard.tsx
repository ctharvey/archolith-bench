import React from 'react';
import { KpiCard, Pill } from '@/ui';
import { cardUrl } from '@/domain/slug';
import type { DeckDisplay } from './mappers';

interface DeckCardProps {
  deck: DeckDisplay;
}

export function DeckCard({ deck }: DeckCardProps) {
  return (
    <KpiCard
      title={deck.name}
      subtitle={deck.format}
      value={deck.totalValueDisplay}
      href={`/deck/${deck.id}`}
      imageUrl={deck.topCardImageUrl ?? undefined}
      imageAlt={deck.topCardName ?? undefined}
    >
      <div className="flex gap-2 mt-2">
        <Pill>{deck.cardCountDisplay}</Pill>
        <Pill>{deck.uniqueCardsDisplay}</Pill>
      </div>
      {deck.updatedAtDisplay !== '—' && (
        <p className="text-xs text-muted-foreground mt-1">Updated {deck.updatedAtDisplay}</p>
      )}
    </KpiCard>
  );
}
