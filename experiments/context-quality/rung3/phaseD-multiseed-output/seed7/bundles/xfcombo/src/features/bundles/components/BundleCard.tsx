import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discount = bundle.discountPercent;
    const originalPrice = bundle.originalPrice;
    const bundlePrice = bundle.bundlePrice;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {discount != null && (
                    <span className={s.discountBadge}>-{discount.toFixed(0)}%</span>
                )}
            </div>

            <div className={s.description}>{bundle.description}</div>

            <div className={s.pricing}>
                {originalPrice != null && (
                    <span className={s.originalPrice}>${originalPrice.toFixed(2)}</span>
                )}
                {bundlePrice != null && (
                    <span className={s.bundlePrice}>${bundlePrice.toFixed(2)}</span>
                )}
            </div>

            {bundle.items != null && bundle.items.length > 0 && (
                <div className={s.items}>
                    <span className={s.itemsLabel}>Includes:</span>
                    <ul className={s.itemsList}>
                        {bundle.items.map((item, i) => (
                            <li key={i} className={s.item}>{item}</li>
                        ))}
                    </ul>
                </div>
            )}
        </Box>
    );
}
