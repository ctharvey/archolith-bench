import type { BundleDto } from '@/data/apiClient';
import { Box, Pill } from '@/ui';
import s from './BundleTile.module.css';

interface BundleTileProps {
    bundle: BundleDto;
}

export default function BundleTile({ bundle }: BundleTileProps) {
    const discountPercent = bundle.discountPercent;
    const hasDiscount = discountPercent != null && discountPercent > 0;

    return (
        <Box className={s.tile}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {hasDiscount && (
                    <Pill variant="success" className={s.discountPill}>
                        -{discountPercent!.toFixed(0)}%
                    </Pill>
                )}
            </div>
            <div className={s.details}>
                <div className={s.priceRow}>
                    <span className={s.priceLabel}>Price</span>
                    <span className={s.priceValue}>
                        {bundle.price != null ? `$${bundle.price.toFixed(2)}` : '—'}
                    </span>
                </div>
                {bundle.originalPrice != null && (
                    <div className={s.priceRow}>
                        <span className={s.priceLabel}>Original</span>
                        <span className={s.originalPrice}>
                            ${bundle.originalPrice.toFixed(2)}
                        </span>
                    </div>
                )}
                {bundle.itemCount != null && (
                    <div className={s.priceRow}>
                        <span className={s.priceLabel}>Items</span>
                        <span className={s.itemCount}>{bundle.itemCount}</span>
                    </div>
                )}
            </div>
            {bundle.description && (
                <p className={s.description}>{bundle.description}</p>
            )}
        </Box>
    );
}
