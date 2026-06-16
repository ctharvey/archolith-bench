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
          <div className={s.imageWrap}>
            {promo.logoUrl ? (
              <img
                src={promo.logoUrl}
                alt={promo.name}
                className={s.logo}
                loading="lazy"
              />
            ) : (
              <div className={s.placeholder}>
                <span>{promo.name.charAt(0)}</span>
              </div>
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
