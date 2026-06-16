import { Box } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discountPercent = bundle.discountPercent ?? 0;
    const savings = bundle.savings ?? 0;
    const marketPrice = bundle.marketPrice ?? 0;
    const bundlePrice = bundle.bundlePrice ?? 0;

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <div className={s.discountBadge}>
                    <span className={s.discountValue}>{discountPercent.toFixed(1)}%</span>
                    <span className={s.discountLabel}>OFF</span>
                </div>
                <div className={s.savings}>Save ${savings.toFixed(2)}</div>
            </div>
            <div className={s.body}>
                <h3 className={s.name}>{bundle.name}</h3>
                {bundle.description && (
                    <p className={s.description}>{bundle.description}</p>
                )}
                <div className={s.pricing}>
                    <div className={s.priceRow}>
                        <span className={s.priceLabel}>Bundle</span>
                        <span className={s.bundlePrice}>${bundlePrice.toFixed(2)}</span>
                    </div>
                    <div className={s.priceRow}>
                        <span className={s.priceLabel}>Market</span>
                        <span className={s.marketPrice}>${marketPrice.toFixed(2)}</span>
                    </div>
                </div>
            </div>
            {bundle.products && bundle.products.length > 0 && (
                <div className={s.products}>
                    <span className={s.productsLabel}>Includes:</span>
                    <ul className={s.productList}>
                        {bundle.products.slice(0, 5).map((p, i) => (
                            <li key={i} className={s.productItem}>{p}</li>
                        ))}
                        {bundle.products.length > 5 && (
                            <li className={s.productItem}>+{bundle.products.length - 5} more</li>
                        )}
                    </ul>
                </div>
            )}
        </Box>
    );
}
