import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discount = bundle.discountPercent;
    const discountLabel = discount != null ? `${discount.toFixed(1)}% off` : null;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {discountLabel && (
                    <span className={s.discountBadge}>{discountLabel}</span>
                )}
            </div>
            <div className={s.details}>
                {bundle.originalPrice != null && (
                    <div className={s.priceRow}>
                        <span className={s.label}>Original</span>
                        <span className={s.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
                    </div>
                )}
                {bundle.bundlePrice != null && (
                    <div className={s.priceRow}>
                        <span className={s.label}>Bundle</span>
                        <span className={s.bundlePrice}>${bundle.bundlePrice.toFixed(2)}</span>
                    </div>
                )}
                {bundle.savings != null && (
                    <div className={s.priceRow}>
                        <span className={s.label}>Savings</span>
                        <span className={s.savings}>${bundle.savings.toFixed(2)}</span>
                    </div>
                )}
            </div>
            {bundle.description && (
                <p className={s.description}>{bundle.description}</p>
            )}
            {bundle.products && bundle.products.length > 0 && (
                <div className={s.products}>
                    <span className={s.productsLabel}>Includes:</span>
                    <ul className={s.productList}>
                        {bundle.products.map((p, i) => (
                            <li key={i} className={s.productItem}>{p}</li>
                        ))}
                    </ul>
                </div>
            )}
        </Box>
    );
}
