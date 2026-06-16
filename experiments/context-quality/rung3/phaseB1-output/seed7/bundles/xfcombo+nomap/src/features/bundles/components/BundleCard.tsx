import { Box } from '@/ui';
import type { BundleDto } from '../types';
import s from './BundleCard.module.css';

interface BundleCardProps {
    bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
    const discountColor = bundle.discountPercent != null
        ? bundle.discountPercent >= 20
            ? 'var(--color-green)'
            : bundle.discountPercent >= 10
                ? 'var(--color-yellow)'
                : 'var(--color-text-secondary)'
        : 'var(--color-text-muted)';

    return (
        <Box className={s.card}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {bundle.discountPercent != null && (
                    <span
                        className={s.discount}
                        style={{ color: discountColor }}
                    >
                        -{bundle.discountPercent}%
                    </span>
                )}
            </div>
            <div className={s.details}>
                {bundle.description && (
                    <p className={s.description}>{bundle.description}</p>
                )}
                <div className={s.priceRow}>
                    {bundle.originalPrice != null && (
                        <span className={s.originalPrice}>
                            ${bundle.originalPrice.toFixed(2)}
                        </span>
                    )}
                    {bundle.price != null && (
                        <span className={s.price}>
                            ${bundle.price.toFixed(2)}
                        </span>
                    )}
                </div>
                {bundle.itemsCount != null && (
                    <span className={s.itemsCount}>
                        {bundle.itemsCount} item{bundle.itemsCount !== 1 ? 's' : ''}
                    </span>
                )}
            </div>
        </Box>
    );
}
