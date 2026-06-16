import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, loading, error } = useBundlesData();

    const { avgDiscount, totalSavings, bundleCount } = useMemo(() => {
        if (!bundles.length) return { avgDiscount: null, totalSavings: null, bundleCount: 0 };
        const discounts = bundles.map(b => b.discountPercent);
        const savings = bundles.map(b => b.savings);
        return {
            avgDiscount: discounts.reduce((a, b) => a + b, 0) / discounts.length,
            totalSavings: savings.reduce((a, b) => a + b, 0),
            bundleCount: bundles.length,
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
                        Curated product bundles with savings
                    </span>
                }
            >
                <span>Bundles</span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Bundles"
                    value={bundleCount}
                    sub="available"
                    tip="Number of active product bundles"
                />
                <KpiCard
                    label="Avg Discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub="off retail"
                    tip="Average discount across all bundles"
                />
                <KpiCard
                    label="Total Savings"
                    value={totalSavings != null ? `$${totalSavings.toFixed(2)}` : '—'}
                    sub="combined"
                    tip="Total savings if you bought all bundles"
                />
            </KpiStrip>

            {bundles.length === 0 ? (
                <Box className={s.emptyBox}>
                    <div className={s.emptyMsg}>No bundles available right now.</div>
                    <div className="mono xs muted">Check back later for new deals.</div>
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
