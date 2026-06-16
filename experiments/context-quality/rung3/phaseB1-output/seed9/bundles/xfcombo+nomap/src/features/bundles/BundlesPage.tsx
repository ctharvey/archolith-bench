import { useEffect, useMemo, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import BundleCard from './components/BundleCard';
import { useBundlesData } from './useBundlesData';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
    const { bundles, total, loading, error } = useBundlesData();

    // ── Server-side search ────────────────────────────────────────────────────
    const [rawSearch, setRawSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [searchResults, setSearchResults] = useState<BundleDto[]>([]);
    const [searchTotal, setSearchTotal] = useState(0);
    const [searchLoading, setSearchLoading] = useState(false);
    const searchAbortRef = useRef<AbortController | null>(null);

    // Debounce raw input → 350ms
    useEffect(() => {
        const q = rawSearch.trim();
        if (!q) {
            setDebouncedSearch('');
            return;
        }
        const t = setTimeout(() => setDebouncedSearch(q), 350);
        return () => clearTimeout(t);
    }, [rawSearch]);

    // Fetch when debounced query changes
    useEffect(() => {
        if (!debouncedSearch) {
            setSearchResults([]);
            setSearchTotal(0);
            return;
        }
        searchAbortRef.current?.abort();
        const ac = new AbortController();
        searchAbortRef.current = ac;
        setSearchLoading(true);

        api.getBundles({ name: debouncedSearch, page: 0, size: 200 }, ac.signal)
            .then(res => {
                if (ac.signal.aborted) return;
                setSearchResults(res.data);
                setSearchTotal(res.total);
                setSearchLoading(false);
            })
            .catch(err => {
                if (err instanceof DOMException && err.name === 'AbortError') return;
                if (!ac.signal.aborted) setSearchLoading(false);
            });

        return () => { ac.abort(); };
    }, [debouncedSearch]);

    // Cleanup on unmount
    useEffect(() => { return () => { searchAbortRef.current?.abort(); }; }, []);

    const isSearching = rawSearch.trim().length > 0;

    // ── KPIs ──────────────────────────────────────────────────────────────────
    const { avgDiscount, avgSavings, bundleCount } = useMemo(() => {
        const withDiscount = bundles.filter(b => b.discountPercent != null);
        const avgDisc = withDiscount.length > 0
            ? withDiscount.reduce((sum, b) => sum + b.discountPercent!, 0) / withDiscount.length
            : null;
        const avgSave = withDiscount.length > 0
            ? withDiscount.reduce((sum, b) => sum + (b.retailPrice - b.bundlePrice), 0) / withDiscount.length
            : null;
        return {
            avgDiscount: avgDisc,
            avgSavings: avgSave,
            bundleCount: bundles.length,
        };
    }, [bundles]);

    if (loading) {
        return (
            <PageMain>
                <PageTitle meta={<span className="mono xs muted">loading…</span>}>
                    <span>Bundles<span className={s.accentItalic}>, save more.</span></span>
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
                        Curated product bundles with exclusive discounts
                    </span>
                }
            >
                <span>
                    Bundles<span className={s.accentItalic}>, save more.</span>
                </span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Bundles"
                    value={bundleCount}
                    sub={`${total || bundles.length} available`}
                    tip="Total number of product bundles"
                />
                <KpiCard
                    label="Avg Discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub={bundleCount > 0 ? 'off retail' : 'no data'}
                    tip="Average discount percentage across all bundles"
                />
                <KpiCard
                    label="Avg Savings"
                    value={avgSavings != null ? `$${avgSavings.toFixed(2)}` : '—'}
                    sub={bundleCount > 0 ? 'per bundle' : 'no data'}
                    tip="Average dollar savings per bundle"
                />
            </KpiStrip>

            {/* ── Search bar (always visible) ─────────────────────────────── */}
            <div className={s.searchBar}>
                <input
                    type="text"
                    placeholder="Search bundles…"
                    value={rawSearch}
                    onChange={e => setRawSearch(e.target.value)}
                    className={s.searchInput}
                />
                {rawSearch && (
                    <button
                        className={s.searchClear}
                        onClick={() => setRawSearch('')}
                        aria-label="Clear search"
                    >
                        ✕
                    </button>
                )}
            </div>

            {/* ── Search results ──────────────────────────────────────────── */}
            {isSearching ? (
                searchLoading ? (
                    <Grid cols={3}>
                        {Array.from({ length: 6 }).map((_, i) => (
                            <Skeleton key={i} width="100%" height={280} />
                        ))}
                    </Grid>
                ) : searchResults.length === 0 ? (
                    debouncedSearch ? (
                        <Box className={s.emptySearch}>
                            <div className={s.emptySearchMsg}>
                                No bundles found for <em>"{debouncedSearch}"</em>
                            </div>
                        </Box>
                    ) : null
                ) : (
                    <>
                        <div className={s.searchResultsMeta}>
                            <span className={`mono xs ${s.metaText}`}>
                                {searchResults.length}{searchTotal > searchResults.length ? ` of ${searchTotal}` : ''} result{searchResults.length !== 1 ? 's' : ''} for <em>"{debouncedSearch}"</em>
                            </span>
                        </div>
                        <Grid cols={3}>
                            {searchResults.map(bundle => (
                                <BundleCard key={bundle.id} bundle={bundle} />
                            ))}
                        </Grid>
                    </>
                )
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
