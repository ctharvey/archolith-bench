import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, total, loading, error } = useBundlesData();

    const avgDiscount = useMemo(() => {
        const discounts = bundles
            .filter(b => b.discountPercent != null)
            .map(b => b.discountPercent!);
        if (discounts.length === 0) return null;
        return discounts.reduce((a, b) => a + b, 0) / discounts.length;
    }, [bundles]);

    const maxDiscount = useMemo(() => {
        const discounts = bundles
            .filter(b => b.discountPercent != null)
            .map(b => b.discountPercent!);
        if (discounts.length === 0) return null;
        return Math.max(...discounts);
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
                        Product bundles with discounted pricing
                    </span>
                }
            >
                <span>Bundles</span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Total Bundles"
                    value={total || bundles.length}
                    sub="active bundles"
                    tip="Number of product bundles currently available"
                />
                <KpiCard
                    label="Avg Discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub="across all bundles"
                    tip="Average discount percentage across all bundles"
                />
                <KpiCard
                    label="Best Discount"
                    value={maxDiscount != null ? `${maxDiscount.toFixed(1)}%` : '—'}
                    sub="highest discount"
                    tip="Highest discount percentage available"
                />
            </KpiStrip>

            {bundles.length === 0 ? (
                <Box className={s.emptyBox}>
                    <div className={s.emptyMsg}>No bundles available yet</div>
                    <div className="mono xs muted">Check back later for bundle deals.</div>
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
