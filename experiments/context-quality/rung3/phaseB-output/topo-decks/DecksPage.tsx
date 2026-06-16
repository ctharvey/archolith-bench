import { PageMain, PageTitle, Box, KpiCard, KpiStrip } from '@/ui';
import { useDecksData } from './useDecksData';
import s from './DecksPage.module.css';

export default function DecksPage() {
    const { decks, loading, error } = useDecksData();

    if (loading) return <PageMain><PageTitle meta={<span className="mono xs muted">loading…</span>}>Decks</PageTitle></PageMain>;
    if (error) return <PageMain><PageTitle>Decks</PageTitle><Box className={s.errorBox}><div className={s.errorText}>{error}</div></Box></PageMain>;

    const totalValue = decks.reduce((sum, d) => sum + d.totalValueNum, 0);
    const formats = [...new Set(decks.map(d => d.format))].sort();
    const largest = decks.toSorted((a, b) => b.totalValueNum - a.totalValueNum)[0];

    return (
        <PageMain>
            <PageTitle meta={<span className={`mono xs ${s.metaMuted}`}>{decks.length} decks</span>}>Decks</PageTitle>
            <KpiStrip>
                <KpiCard label="Decks" value={decks.length} sub="total" />
                <KpiCard label="Combined value" value={`$${(totalValue / 1_000_000_000).toFixed(1)}B`} sub="market" />
                <KpiCard label="Formats" value={formats.length} sub="active" />
                <KpiCard label="Largest" value={largest?.name ?? '—'} sub={largest?.totalValue} />
                <KpiCard label="Most cards" value={decks.toSorted((a, b) => b.cardCount - a.cardCount)[0]?.cardCount ?? 0} sub="deck size" />
            </KpiStrip>
            <Box style={{overflow:'hidden'}}>
                <table className="wf-table">
                    <thead><tr><th>Deck</th><th>Format</th><th className="num">Cards</th><th className="num">Market value</th><th className="num">Top card</th></tr></thead>
                    <tbody>
                        {decks.map(d => (
        <tr key={d.id} className="clickable-row">
          <td style={{color:'var(--t-1)',fontWeight:500}}>{d.name}</td>
                            <td style={{color:'var(--t-4)',fontFamily:'var(--mono)',fontSize:'11px'}}>{d.format}</td>
                            <td className="num mono">{d.cardCount}</td>
                            <td className="num mono">{d.totalValue}</td>
                            <td className="num mono" style={{color:'var(--t-3)'}}>{d.topCard} ({d.topCardValue})</td>
                        </tr>
                        ))}
                    </tbody>
                </table>
            </Box>
        </PageMain>
    );
}
