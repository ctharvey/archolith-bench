import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discountPercent = bundle.discountPercent ?? 0;
    const savings = bundle.savings ?? 0;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {discountPercent > 0 && (
                    <span className={s.discountBadge}>-{discountPercent.toFixed(0)}%</span>
                )}
            </div>
            <div className={s.details}>
                <div className={s.priceRow}>
                    <span className={s.originalPrice}>${bundle.originalPrice?.toFixed(2)}</span>
                    <span className={s.bundlePrice}>${bundle.bundlePrice?.toFixed(2)}</span>
                </div>
                {savings > 0 && (
                    <div className={s.savings}>
                        Save ${savings.toFixed(2)}
                    </div>
                )}
            </div>
            {bundle.description && (
                <p className={s.description}>{bundle.description}</p>
            )}
            <div className={s.footer}>
                <span className={`mono xs ${s.itemsCount}`}>
                    {bundle.itemCount ?? 0} item{(bundle.itemCount ?? 0) !== 1 ? 's' : ''}
                </span>
            </div>
        </Box>
    );
}
