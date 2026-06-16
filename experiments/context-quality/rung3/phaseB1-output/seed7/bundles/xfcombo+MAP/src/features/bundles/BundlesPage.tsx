import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, SegControl, Box, Grid, Skeleton } from '@/ui';
import BundleTile from './components/BundleTile';
import { useBundlesData } from './useBundlesData';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';
import s from './BundlesPage.module.css';

type Tab = 'all' | 'best' | 'new';

const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All bundles' },
    { key: 'best', label: 'Best deals' },
    { key: 'new', label: 'Newest' },
];

export default function BundlesPage() {
    const [tab, setTab] = useState<Tab>('all');
    const { bundles, total, loading, error } = useBundlesData();

    // ── Derived KPIs ──────────────────────────────────────────────────────
    const { avgDiscount, totalSavings, bundleCount } = useMemo(() => {
        const withDiscount = bundles.filter(b => b.discountPercent != null && b.discountPercent > 0);
        const avg = withDiscount.length > 0
            ? withDiscount.reduce((sum, b) => sum + b.discountPercent!, 0) / withDiscount.length
            : 0;
        const savings = bundles.reduce((sum, b) => sum + (b.savings ?? 0), 0);
        return {
            avgDiscount: avg,
            totalSavings: savings,
            bundleCount: bundles.length,
        };
    }, [bundles]);

    // ── Filtered lists ────────────────────────────────────────────────────
    const bestDeals = useMemo(() =>
        bundles
            .filter(b => b.discountPercent != null && b.discountPercent > 0)
            .sort((a, b) => (b.discountPercent ?? 0) - (a.discountPercent ?? 0))
            .slice(0, 12),
        [bundles]
    );

    const newest = useMemo(() =>
        [...bundles]
            .sort((a, b) => new Date(b.createdAt ?? 0).getTime() - new Date(a.createdAt ?? 0).getTime())
            .slice(0, 12),
        [bundles]
    );

    if (loading) {
        return (
            <PageMain>
                <PageTitle meta={<span className="mono xs muted">loading…</span>}>
                    <span>Bundles<span className={s.accentItalic}>, best value.</span></span>
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
                        Browse product bundles and find the best discounts
                    </span>
                }
            >
                <span>
                    Bundles<span className={s.accentItalic}>, best value.</span>
                </span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Bundles"
                    value={bundleCount}
                    sub={`${total} available`}
                    tip="Total number of product bundles"
                />
                <KpiCard
                    label="Avg discount"
                    value={avgDiscount > 0 ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub={avgDiscount > 0 ? 'across all bundles' : 'no discounts yet'}
                    tip="Average discount percentage across all bundles"
                />
                <KpiCard
                    label="Total savings"
                    value={totalSavings > 0 ? `$${totalSavings.toFixed(2)}` : '—'}
                    sub={totalSavings > 0 ? 'if bought separately' : 'no data'}
                    tip="Total savings compared to buying items individually"
                />
            </KpiStrip>

            {/* ── Tab bar ──────────────────────────────────────────────── */}
            <div className={s.tabBar}>
                <SegControl
                    options={TABS.map(t => t.key)}
                    value={tab}
                    onChange={k => setTab(k as Tab)}
                />
            </div>

            {/* ═══ All bundles view ═══ */}
            {tab === 'all' && (
                bundles.length === 0 ? (
                    <Box className={s.emptyBox}>
                        <div className={s.emptyMsg}>No bundles available yet</div>
                        <div className="mono xs muted">Check back later for new bundle deals.</div>
                    </Box>
                ) : (
                    <Grid cols={3}>
                        {bundles.map(bundle => (
                            <BundleTile key={bundle.id} bundle={bundle} />
                        ))}
                    </Grid>
                )
            )}

            {/* ═══ Best deals view ═══ */}
            {tab === 'best' && (
                bestDeals.length === 0 ? (
                    <Box className={s.emptyBox}>
                        <div className={s.emptyMsg}>No discounted bundles yet</div>
                        <div className="mono xs muted">Discounted bundles will appear here.</div>
                    </Box>
                ) : (
                    <Grid cols={3}>
                        {bestDeals.map(bundle => (
                            <BundleTile key={bundle.id} bundle={bundle} />
                        ))}
                    </Grid>
                )
            )}

            {/* ═══ Newest view ═══ */}
            {tab === 'new' && (
                newest.length === 0 ? (
                    <Box className={s.emptyBox}>
                        <div className={s.emptyMsg}>No bundles yet</div>
                        <div className="mono xs muted">New bundles will appear here.</div>
                    </Box>
                ) : (
                    <Grid cols={3}>
                        {newest.map(bundle => (
                            <BundleTile key={bundle.id} bundle={bundle} />
                        ))}
                    </Grid>
                )
            )}
        </PageMain>
    );
}
