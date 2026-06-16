import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discount = bundle.discountPercent;
    const savings = bundle.retailPrice - bundle.bundlePrice;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {discount != null && (
                    <span className={s.discountBadge}>-{discount.toFixed(0)}%</span>
                )}
            </div>

            <div className={s.products}>
                {bundle.products?.slice(0, 4).map(p => (
                    <span key={p.id} className={s.productChip}>{p.name}</span>
                ))}
                {bundle.products && bundle.products.length > 4 && (
                    <span className={s.moreChip}>+{bundle.products.length - 4} more</span>
                )}
            </div>

            <div className={s.pricing}>
                <div className={s.priceRow}>
                    <span className={s.retailPrice}>${bundle.retailPrice.toFixed(2)}</span>
                    <span className={s.bundlePrice}>${bundle.bundlePrice.toFixed(2)}</span>
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
        </Box>
    );
}
