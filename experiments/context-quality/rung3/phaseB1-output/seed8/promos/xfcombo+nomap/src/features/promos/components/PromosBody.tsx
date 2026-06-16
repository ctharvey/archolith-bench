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
  filtered: PromoSet[];
}

export default function PromosBody({ filtered }: PromosBodyProps) {
  if (filtered.length === 0) {
    return <div className={s.empty}>No promo sets match your filters.</div>;
  }

  return (
    <div className={s.grid}>
      {filtered.map(promo => (
        <a key={promo.id} href={`/sets/${promo.id}`} className={s.card}>
          <div className={s.imageWrap}>
            {promo.logoUrl ? (
              <img
                className={s.logo}
                src={promo.logoUrl}
                alt={promo.name}
                loading="lazy"
              />
            ) : (
              <div className={s.placeholder}>{promo.name.charAt(0)}</div>
            )}
          </div>
          <div className={s.info}>
            <h3 className={s.name}>{promo.name}</h3>
            <div className={s.meta}>
              <span className={s.year}>{promo.releaseYear}</span>
              <span className={s.dot}>·</span>
              <span className={s.cards}>{promo.cardCount} cards</span>
            </div>
            {promo.serie && <span className={s.serie}>{promo.serie}</span>}
          </div>
        </a>
      ))}
    </div>
  );
}
