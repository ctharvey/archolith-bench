import s from './PromosBody.module.css';

interface PromoSet {
  id: string;
  name: string;
  code: string;
  serie: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
}

interface PromosBodyProps {
  promos: PromoSet[];
}

export default function PromosBody({ promos }: PromosBodyProps) {
  if (promos.length === 0) {
    return <div className={s.empty}>No promo sets match your filters.</div>;
  }

  return (
    <div className={s.grid}>
      {promos.map(promo => (
        <div key={promo.id} className={s.card}>
          <div className={s.imageWrap}>
            {promo.logoUrl ? (
              <img
                className={s.logo}
                src={promo.logoUrl}
                alt={`${promo.name} logo`}
                loading="lazy"
              />
            ) : (
              <div className={s.placeholder}>
                <span className={s.placeholderText}>{promo.code}</span>
              </div>
            )}
          </div>
          <div className={s.info}>
            <h3 className={s.name}>{promo.name}</h3>
            <div className={s.meta}>
              <span className={s.year}>{promo.releaseYear}</span>
              <span className={s.dot}>·</span>
              <span className={s.cardCount}>{promo.cardCount} cards</span>
            </div>
            <span className={s.serie}>{promo.serie}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
