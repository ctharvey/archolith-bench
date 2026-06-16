import { useEffect, useMemo, useRef, useState } from 'react';
import { PageMain, PageTitle, KpiCard, KpiStrip, Box, Grid, Skeleton } from '@/ui';
import DeckCard from './components/DeckCard';
import { useDecksData } from './useDecksData';
import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import s from './DecksPage.module.css';

export default function DecksPage() {
    const { decks, total, loading, loadingMore, hasMore, loadMore, error } = useDecksData();

    // ── Server-side search ────────────────────────────────────────────────────
    const [rawSearch, setRawSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [searchResults, setSearchResults] = useState<DeckDto[]>([]);
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

        api.getDecks({ deckName: debouncedSearch, page: 0, size: 200 }, ac.signal)
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
    const { avgValue, totalValue, deckCount } = useMemo(() => {
        const values = decks
            .filter(d => d.totalMarketValue != null)
            .map(d => d.totalMarketValue!);
        const sum = values.reduce((a, b) => a + b, 0);
        return {
            avgValue: values.length > 0 ? sum / values.length : null,
            totalValue: sum,
            deckCount: values.length,
        };
    }, [decks]);

    if (loading) {
        return (
            <PageMain>
                <PageTitle meta={<span className="mono xs muted">loading…</span>}>
                    <span>Decks</span>
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
                <PageTitle>Decks</PageTitle>
                <Box className={s.errorBox}>
                    <div className={s.errorMsg}>{error}</div>
                    <div className="mono xs muted">Deck data will appear here once decks are synced.</div>
                </Box>
            </PageMain>
        );
    }

    return (
        <PageMain>
            <PageTitle
                meta={
                    <span className={`mono xs ${s.metaText}`}>
                        Browse decks and their total market values
                    </span>
                }
            >
                <span>Decks</span>
            </PageTitle>

            <KpiStrip>
                <KpiCard
                    label="Decks"
                    value={total || decks.length}
                    sub={`${deckCount} with value`}
                    tip="Total number of decks tracked"
                />
                <KpiCard
                    label="Avg Value"
                    value={avgValue != null ? `$${avgValue.toFixed(2)}` : '—'}
                    sub={deckCount > 0 ? `${deckCount} decks` : 'no data'}
                    tip="Average total market value across all decks"
                />
                <KpiCard
                    label="Total Value"
                    value={totalValue != null ? `$${totalValue.toFixed(2)}` : '—'}
                    sub={deckCount > 0 ? `${deckCount} decks` : 'no data'}
                    tip="Sum of all deck market values"
                />
            </KpiStrip>

            {/* ── Search bar (always visible) ─────────────────────────────── */}
            <div className={s.searchBar}>
                <input
                    type="text"
                    placeholder="Search decks…"
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

            {/* ── Search results ─────────────────────────────────────────── */}
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
                                No decks found for <em>"{debouncedSearch}"</em>
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
                            {searchResults.map(deck => (
                                <DeckCard key={deck.id} deck={deck} />
                            ))}
                        </Grid>
                    </>
                )
            ) : (
                <>
                    {/* ── Deck grid ──────────────────────────────────────────── */}
                    <Grid cols={3}>
                        {decks.map(deck => (
                            <DeckCard key={deck.id} deck={deck} />
                        ))}
                    </Grid>

                    {hasMore && (
                        <div className={s.loadMoreWrap}>
                            <button
                                className={s.loadMoreBtn}
                                onClick={loadMore}
                                disabled={loadingMore}
                            >
                                {loadingMore ? 'Loading…' : 'Load more'}
                            </button>
                        </div>
                    )}
                </>
            )}
        </PageMain>
    );
}
