import type { PromoCard } from '../types';
import PromoCard from './PromoCard';
import css from './PromoGrid.module.css';

interface PromoGridProps {
  cards: PromoCard[];
}

export default function PromoGrid({ cards }: PromoGridProps) {
  return (
    <div>
      <div className={css.header}>
        <h2 className={css.title}>Promo Cards</h2>
        <span className={css.count}>{cards.length} cards</span>
      </div>
      <div className={css.grid}>
        {cards.map(card => (
          <PromoCard key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}
