import { useEffect, useMemo, useRef, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, SegControl, Box, Grid, Skeleton } from '@/ui';
import BundleTile from './components/BundleTile';
import { useBundlesData } from './useBundlesData';
import { api } from '@/data/apiClient';
import type { BundleDto } from '@/data/apiClient';
import s from './BundlesPage.module.css';

type Tab = 'all' | 'best' | 'new';

const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All bundles' },
    { key: 'best', label: 'Best discounts' },
    { key: 'new', label: 'Newest' },
];

export default function BundlesPage() {
    const [tab, setTab] = useState<Tab>('all');
    const { bundles, total, loading, loadingMore, hasMore, loadMore, error } = useBundlesData();

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

    // ── Market KPIs ──────────────────────────────────────────────────────────
    const { avgDiscount, avgPrice, bundleCount } = useMemo(() => {
        const withDiscount = bundles.filter(b => b.discountPercent != null && b.price != null);
        const sumDiscount = withDiscount.reduce((acc, b) => acc + (b.discountPercent ?? 0), 0);
        const sumPrice = withDiscount.reduce((acc, b) => acc + (b.price ?? 0), 0);
        return {
            avgDiscount: withDiscount.length > 0 ? sumDiscount / withDiscount.length : null,
            avgPrice: withDiscount.length > 0 ? sumPrice / withDiscount.length : null,
            bundleCount: bundles.length,
        };
    }, [bundles]);

    // ── Sorted bundles for tabs ─────────────────────────────────────────────
    const sortedBundles = useMemo(() => {
        if (tab === 'best') {
            return [...bundles]
                .filter(b => b.discountPercent != null)
                .sort((a, b) => (b.discountPercent ?? 0) - (a.discountPercent ?? 0));
        }
        if (tab === 'new') {
            return [...bundles].sort((a, b) => {
                const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
                const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
                return dateB - dateA;
            });
        }
        return bundles;
    }, [bundles, tab]);

    if (loading) {
        return (
            <PageMain>
                <PageTitle meta={<span className="mono xs muted">loading…</span>}>
                    <span>Bundles<span className={s.accentItalic}>, best deals.</span></span>
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
                        Curated product bundles with discounted pricing
                    </span>
                }
            >
                <span>
                    Bundles<span className={s.accentItalic}>, best deals.</span>
                </span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Bundles"
                    value={bundleCount}
                    sub={`${total || bundles.length} total`}
                    tip="Number of product bundles available"
                />
                <KpiCard
                    label="Avg discount"
                    value={avgDiscount != null ? `${avgDiscount.toFixed(1)}%` : '—'}
                    sub={avgPrice != null ? `avg $${avgPrice.toFixed(2)}` : 'no data'}
                    tip="Average discount percentage across all bundles"
                />
                <KpiCard
                    label="Avg price"
                    value={avgPrice != null ? `$${avgPrice.toFixed(2)}` : '—'}
                    sub={bundleCount > 0 ? `${bundleCount} bundles` : 'no data'}
                    tip="Average bundle price"
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

            {/* ── Search results (bypasses tabs) ─────────────────────────── */}
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
                                <BundleTile key={bundle.id} bundle={bundle} />
                            ))}
                        </Grid>
                    </>
                )
            ) : (
                <>
                    {/* ── Tab bar ──────────────────────────────────────────── */}
                    <div className={s.tabBar}>
                        <SegControl
                            options={TABS.map(t => t.key)}
                            value={tab}
                            onChange={k => setTab(k as Tab)}
                        />
                    </div>

                    {/* ═══ All bundles view ═══ */}
                    {tab === 'all' && (
                        <Grid cols={3}>
                            {sortedBundles.map(bundle => (
                                <BundleTile key={bundle.id} bundle={bundle} />
                            ))}
                        </Grid>
                    )}

                    {/* ═══ Best discounts view ═══ */}
                    {tab === 'best' && (
                        sortedBundles.length === 0 ? (
                            <Box className={s.emptyBox}>
                                <div className={s.emptyTitle}>No discounted bundles yet</div>
                                <div className="mono xs muted">Bundles with discounts will appear here.</div>
                            </Box>
                        ) : (
                            <Grid cols={3}>
                                {sortedBundles.map(bundle => (
                                    <BundleTile key={bundle.id} bundle={bundle} />
                                ))}
                            </Grid>
                        )
                    )}

                    {/* ═══ Newest view ═══ */}
                    {tab === 'new' && (
                        sortedBundles.length === 0 ? (
                            <Box className={s.emptyBox}>
                                <div className={s.emptyTitle}>No bundles yet</div>
                                <div className="mono xs muted">New bundles will appear here.</div>
                            </Box>
                        ) : (
                            <Grid cols={3}>
                                {sortedBundles.map(bundle => (
                                    <BundleTile key={bundle.id} bundle={bundle} />
                                ))}
                            </Grid>
                        )
                    )}

                    {/* ── Load more ──────────────────────────────────────────── */}
                    {hasMore && !isSearching && (
                        <div className={s.loadMoreWrap}>
                            <button
                                className={s.loadMoreBtn}
                                onClick={loadMore}
                                disabled={loadingMore}
                            >
                                {loadingMore ? 'Loading…' : 'Load more bundles'}
                            </button>
                        </div>
                    )}
                </>
            )}
        </PageMain>
    );
}
