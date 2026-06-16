import type { BundleDto } from '@/data/apiClient';
import { Pill } from '@/ui';
import s from './BundleTile.module.css';

interface BundleTileProps {
    bundle: BundleDto;
}

export default function BundleTile({ bundle }: BundleTileProps) {
    const discountPercent = bundle.discountPercent;
    const hasDiscount = discountPercent != null && discountPercent > 0;

    return (
        <div className={s.tile}>
            <div className={s.header}>
                <h3 className={s.name}>{bundle.name}</h3>
                {hasDiscount && (
                    <Pill variant="success">
                        -{discountPercent!.toFixed(0)}%
                    </Pill>
                )}
            </div>

            <div className={s.details}>
                {bundle.productCount != null && (
                    <span className={s.detail}>
                        {bundle.productCount} product{bundle.productCount !== 1 ? 's' : ''}
                    </span>
                )}
                {bundle.category && (
                    <span className={s.detail}>{bundle.category}</span>
                )}
            </div>

            <div className={s.pricing}>
                {bundle.originalPrice != null && (
                    <span className={s.originalPrice}>
                        ${bundle.originalPrice.toFixed(2)}
                    </span>
                )}
                {bundle.price != null && (
                    <span className={s.currentPrice}>
                        ${bundle.price.toFixed(2)}
                    </span>
                )}
            </div>

            {bundle.description && (
                <p className={s.description}>{bundle.description}</p>
            )}

            {bundle.expiresAt && (
                <div className={s.expiry}>
                    <span className="mono xs muted">
                        Expires {new Date(bundle.expiresAt).toLocaleDateString()}
                    </span>
                </div>
            )}
        </div>
    );
}
