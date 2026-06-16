import { Box } from '@/ui';
import type { DeckDto } from '@/data/apiClient';
import s from './DeckCard.module.css';

interface DeckCardProps {
    deck: DeckDto;
}

export default function DeckCard({ deck }: DeckCardProps) {
    const value = deck.totalMarketValue;
    const formattedValue = value != null ? `$${value.toFixed(2)}` : '—';

    return (
        <Box className={s.card}>
            <div className={s.cardHeader}>
                <h3 className={s.deckName}>{deck.name}</h3>
                {deck.format && (
                    <span className={`mono xs ${s.format}`}>{deck.format}</span>
                )}
            </div>
            <div className={s.cardBody}>
                <div className={s.valueLabel}>Total Market Value</div>
                <div className={`mono ${s.value}`}>{formattedValue}</div>
            </div>
            {deck.cardCount != null && (
                <div className={`mono xs ${s.cardCount}`}>
                    {deck.cardCount} card{deck.cardCount !== 1 ? 's' : ''}
                </div>
            )}
        </Box>
    );
}
