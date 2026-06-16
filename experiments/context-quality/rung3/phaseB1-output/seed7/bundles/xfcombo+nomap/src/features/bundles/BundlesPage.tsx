import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, total, loading, error } = useBundlesData();

    const { avgDiscount, maxDiscount, minDiscount, avgPrice } = useMemo(() => {
        if (bundles.length === 0) {
            return { avgDiscount: null, maxDiscount: null, minDiscount: null, avgPrice: null };
        }
        const discounts = bundles
            .filter(b => b.discountPercent != null)
            .map(b => b.discountPercent!);
        const prices = bundles
            .filter(b => b.price != null)
            .map(b => b.price!);
        const sum = (arr: number[]) => arr.reduce((a, b) => a + b, 0);
        return {
            avgDiscount: discounts.length > 0 ? sum(discounts) / discounts.length : null,
            maxDiscount: discounts.length > 0 ? Math.max(...discounts) : null,
            minDiscount: discounts.length > 0 ? Math.min(...discounts) : null,
            avgPrice: prices.length > 0 ? sum(prices) / prices.length : null,
        };
    }, [bundles]);

    if (loading) {
        return (
            <PageMain>
                <PageTitle meta={<span className="mono xs muted">loading…</span>}>
                    <span>Bundles</span>
                </PageTitle>
                <KpiStrip>
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} width="100%" height={106} />
                    ))}
                </KpiStrip>
                <Grid cols={3}>
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} width="100%" height={280} />
                    ))}
                </Grid>
            </PageMain>
        );
    }

    if (error) {
        return (
            <PageMain>
                <PageTitle>Bundles</PageTitle>
                <Box className={s.errorBox}>
                    <div className={s.errorMsg}>{error}</div>
                    <div className="mono xs muted">Bundle data will appear here once available.</div>
                </Box>
            </PageMain>
        );
    }

    return (
        <PageMain>
            <PageTitle
                meta={
                    <span className={`mono xs ${s.metaText}`}>
                        Browse product bundles and their discounts
                    </span>
                }
            >
                <span>Bundles</span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Total Bundles"
                    value={total || bundles.length}
                    sub="available"
                    tip="Number of product bundles tracked"
                />
                <KpiCard
                    label="Avg Discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub={bundles.length > 0 ? `from ${minDiscount?.toFixed(0) ?? '?'}% to ${maxDiscount?.toFixed(0) ?? '?'}%` : 'no data'}
                    tip="Average discount percentage across all bundles"
                />
                <KpiCard
                    label="Avg Price"
                    value={avgPrice != null ? `$${avgPrice.toFixed(2)}` : '—'}
                    sub={`${bundles.length} bundles`}
                    tip="Average bundle price"
                />
            </KpiStrip>

            {bundles.length === 0 ? (
                <Box className={s.emptyBox}>
                    <div className={s.emptyMsg}>No bundles available yet.</div>
                    <div className="mono xs muted">Check back later for new bundle deals.</div>
                </Box>
            ) : (
                <Grid cols={3}>
                    {bundles.map(bundle => (
                        <BundleCard key={bundle.id} bundle={bundle} />
                    ))}
                </Grid>
            )}
        </PageMain>
    );
}
