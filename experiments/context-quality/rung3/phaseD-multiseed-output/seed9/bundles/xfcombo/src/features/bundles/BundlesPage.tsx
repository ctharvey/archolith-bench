import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, total, loading, error } = useBundlesData();

    // ── KPIs ──────────────────────────────────────────────────────────────
    const { avgDiscount, maxDiscount, minDiscount } = useMemo(() => {
        const discounts = bundles
            .filter(b => b.discountPercent != null)
            .map(b => b.discountPercent!);
        if (discounts.length === 0) {
            return { avgDiscount: null, maxDiscount: null, minDiscount: null };
        }
        return {
            avgDiscount: discounts.reduce((a, b) => a + b, 0) / discounts.length,
            maxDiscount: Math.max(...discounts),
            minDiscount: Math.min(...discounts),
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
                    sub={bundles.length > 0 ? `${bundles.length} bundles` : 'no data'}
                    tip="Average discount across all bundles"
                />
                <KpiCard
                    label="Best Discount"
                    value={maxDiscount != null ? `${maxDiscount.toFixed(1)}%` : '—'}
                    sub={minDiscount != null ? `from ${minDiscount.toFixed(1)}%` : '—'}
                    tip="Highest discount available"
                />
            </KpiStrip>

            {bundles.length === 0 ? (
                <Box className={s.emptyBox}>
                    <div className={s.emptyMsg}>No bundles available at this time.</div>
                </Box>
            ) : (
                <Grid cols={3}>
                    {bundles.map(bundle => (
                        <BundleCard key={bundle.id ?? bundle.name} bundle={bundle} />
                    ))}
                </Grid>
            )}
        </PageMain>
    );
}
