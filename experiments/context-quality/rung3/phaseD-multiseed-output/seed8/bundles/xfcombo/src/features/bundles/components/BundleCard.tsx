import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discountPercent = bundle.discountPercent;
    const isGoodDeal = discountPercent >= 20;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.title}>{bundle.name}</h3>
                {isGoodDeal && (
                    <span className={s.badge}>Hot deal</span>
                )}
            </div>
            <div className={s.discountBadge}>
                <span className={s.discountValue}>{discountPercent.toFixed(0)}%</span>
                <span className={s.discountLabel}>OFF</span>
            </div>
            <div className={s.prices}>
                <span className={s.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
                <span className={s.bundlePrice}>${bundle.bundlePrice.toFixed(2)}</span>
            </div>
            <div className={s.savings}>
                Save <strong>${bundle.savings.toFixed(2)}</strong>
            </div>
            {bundle.description && (
                <p className={s.description}>{bundle.description}</p>
            )}
            <div className={s.items}>
                <span className="mono xs muted">{bundle.itemCount} item{bundle.itemCount !== 1 ? 's' : ''}</span>
            </div>
        </Box>
    );
}
