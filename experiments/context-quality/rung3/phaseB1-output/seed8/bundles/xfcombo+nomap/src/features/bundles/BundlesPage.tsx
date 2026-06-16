import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, loading, error } = useBundlesData();

    const { avgDiscount, totalSavings, bundleCount } = useMemo(() => {
        if (!bundles.length) return { avgDiscount: null, totalSavings: null, bundleCount: 0 };
        const discounts = bundles.map(b => b.discountPercent ?? 0);
        const savings = bundles.reduce((sum, b) => sum + (b.savings ?? 0), 0);
        return {
            avgDiscount: discounts.length > 0 ? discounts.reduce((a, b) => a + b, 0) / discounts.length : null,
            totalSavings: savings,
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
                    <div className="mono xs muted">Bundle data will appear here once products are synced.</div>
                </Box>
            </PageMain>
        );
    }

    return (
        <PageMain>
            <PageTitle
                meta={
                    <span className={`mono xs ${s.metaText}`}>
                        Discover product bundles and their discounts
                    </span>
                }
            >
                <span>Bundles</span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Bundles"
                    value={bundleCount}
                    sub={`${bundles.length} available`}
                    tip="Total number of product bundles"
                />
                <KpiCard
                    label="Avg Discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub={bundleCount > 0 ? 'per bundle' : 'no data'}
                    tip="Average discount across all bundles"
                />
                <KpiCard
                    label="Total Savings"
                    value={totalSavings != null ? `$${totalSavings.toFixed(2)}` : '—'}
                    sub={bundleCount > 0 ? 'combined' : 'no data'}
                    tip="Total savings across all bundles"
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
