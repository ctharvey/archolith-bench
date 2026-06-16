import { Box, Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import s from './BundleTile.module.css';

interface BundleTileProps {
    bundle: BundleDto;
}

export default function BundleTile({ bundle }: BundleTileProps) {
    const discount = bundle.discountPercent;
    const hasDiscount = discount != null && discount > 0;

    return (
        <Box className={s.tile}>
            <div className={s.header}>
                <span className={s.name}>{bundle.name}</span>
                {hasDiscount && (
                    <Pill variant="success" className={s.discountPill}>
                        -{discount!.toFixed(0)}%
                    </Pill>
                )}
            </div>

            <div className={s.details}>
                <div className={s.priceRow}>
                    <span className={s.bundlePrice}>${bundle.bundlePrice?.toFixed(2) ?? '—'}</span>
                    {bundle.retailPrice != null && (
                        <span className={s.retailPrice}>${bundle.retailPrice.toFixed(2)}</span>
                    )}
                </div>
                {bundle.savings != null && bundle.savings > 0 && (
                    <div className={s.savings}>
                        Save ${bundle.savings.toFixed(2)}
                    </div>
                )}
            </div>

            {bundle.itemCount != null && (
                <div className={s.itemCount}>
                    {bundle.itemCount} item{bundle.itemCount !== 1 ? 's' : ''}
                </div>
            )}

            {bundle.description && (
                <div className={s.description}>{bundle.description}</div>
            )}
        </Box>
    );
}
