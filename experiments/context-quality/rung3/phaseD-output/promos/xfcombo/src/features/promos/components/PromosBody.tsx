import s from './PromosBody.module.css';

interface PromoSet {
  id: string;
  name: string;
  code: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
}

interface PromosBodyProps {
  promos: PromoSet[];
  totalPromos: number;
}

export default function PromosBody({ promos, totalPromos }: PromosBodyProps) {
  if (promos.length === 0) {
    return (
      <div className={s.empty}>
        <p>No promo sets match your filters.</p>
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {promos.map(promo => (
        <a key={promo.id} href={`/sets/${promo.id}`} className={s.card}>
          {promo.logoUrl && (
            <div className={s.logoWrap}>
              <img src={promo.logoUrl} alt={promo.name} className={s.logo} />
            </div>
          )}
          <div className={s.info}>
            <h3 className={s.name}>{promo.name}</h3>
            <div className={s.meta}>
              <span className={s.year}>{promo.releaseYear}</span>
              <span className={s.dot}>·</span>
              <span className={s.cards}>{promo.cardCount} cards</span>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
