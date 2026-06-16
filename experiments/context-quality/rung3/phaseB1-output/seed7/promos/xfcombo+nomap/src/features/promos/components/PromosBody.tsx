import s from './PromosBody.module.css';

interface PromoData {
  id: string;
  name: string;
  code: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
}

interface PromosBodyProps {
  filtered: PromoData[];
  totalPromos: number;
}

export default function PromosBody({ filtered, totalPromos }: PromosBodyProps) {
  if (filtered.length === 0) {
    return (
      <div className={s.empty}>
        <p>No promo sets match your filters.</p>
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {filtered.map(promo => (
        <a key={promo.id} href={`/promos/${promo.id}`} className={s.card}>
          <div className={s.cardImage}>
            {promo.logoUrl ? (
              <img src={promo.logoUrl} alt={promo.name} className={s.logo} />
            ) : (
              <div className={s.placeholder}>
                <span>{promo.code}</span>
              </div>
            )}
          </div>
          <div className={s.cardInfo}>
            <h3 className={s.cardName}>{promo.name}</h3>
            <div className={s.cardMeta}>
              <span className={s.year}>{promo.releaseYear}</span>
              <span className={s.dot}>·</span>
              <span className={s.count}>{promo.cardCount} cards</span>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
