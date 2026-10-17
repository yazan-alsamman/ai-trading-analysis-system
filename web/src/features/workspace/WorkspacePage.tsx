import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { SideSheet } from '@/components/ui/SideSheet';
import { EmptyState, ErrorState, Loading, OfflineState, Skeleton } from '@/components/ui/StateViews';
import type { AssistantContext } from '@/domain/assistant';
import { getInstrument, INSTRUMENT_SYMBOLS, type InstrumentSymbol } from '@/domain/instruments';
import type { Timeframe } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import { AssistantPanel } from '@/features/assistant/AssistantPanel';
import { useShareRisk } from '@/features/assistant/useAssistantContext';
import { PriceChart } from '@/features/chart/PriceChart';
import { OpportunityPanel } from '@/features/opportunity/OpportunityPanel';
import { useMediaQuery, useNow, useOnlineStatus } from '@/hooks/useEnvironment';
import { useHotkeys } from '@/hooks/useHotkeys';
import { useLiveCandles, useLiveQuotes } from '@/hooks/useMarketData';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { useDemoMembership } from '@/app/membershipStore';
import { getPlan, planIncludes } from '@/domain/membership';
import { cn } from '@/lib/cn';
import { ChartToolbar } from './ChartToolbar';
import { InstrumentHeader } from './InstrumentHeader';
import { Watchlist } from './Watchlist';

type SideTab = 'opportunity' | 'watchlist';

/**
 * Primary trading workspace (SF3, SF4, SF5, SF8, SF9, SF18 + AI Feature 12).
 * Layout by width:
 *   ≥1440px  watchlist | chart | AI panel (fixed-height terminal view)
 *   1024+    chart | tabbed side panel (AI / watchlist) — keeps the chart wide
 *   <1024    stacked: chart, then tabbed panel; page scrolls
 */
export function WorkspacePage() {
  const services = useServices();
  const { activeWorkspace: ws, updateWorkspace, resolvedTheme, timeZone, prefs } = usePreferences();
  const instrument = getInstrument(ws.symbol);
  usePageTitle(`${instrument.display} ${ws.timeframe} · Workspace`);
  const live = useLiveCandles(ws.symbol, ws.timeframe);
  const quotes = useLiveQuotes();
  const now = useNow(1000);
  const online = useOnlineStatus();
  const wide = useMediaQuery('(min-width: 90rem)');
  const [sideTab, setSideTab] = useState<SideTab>('opportunity');
  const [askOpen, setAskOpen] = useState(false);
  const demoPlan = useDemoMembership();
  // Demo plan preview: Essential covers gold only (UI preview, not access control).
  const outsidePlan = demoPlan && !planIncludes(demoPlan.plan, 'tf_alignment') && ws.symbol !== 'XAUUSD';
  const [shareRisk, setShareRisk] = useShareRisk();

  const opportunity = useResource(`opportunity:${ws.symbol}:${ws.timeframe}`, (signal) =>
    services.opportunities.getLatest(ws.symbol, ws.timeframe, { signal }),
  );

  // Same instrument on all timeframes (15m detect · 1h confirm · 4h regime).
  const confluence = useResource(`confluence:${ws.symbol}`, (signal) => services.opportunities.list({ symbol: ws.symbol }, { signal }));
  // All instruments on the active timeframe, for the watchlist AI column.
  const watchSignals = useResource(`watch-ai:${ws.timeframe}`, (signal) => services.opportunities.list({ timeframe: ws.timeframe }, { signal }));
  // Last 24 hourly closes per instrument, for watchlist sparklines.
  const sparkRes = useResource('sparklines', async (signal) => {
    const series = await Promise.all(INSTRUMENT_SYMBOLS.map((s) => services.market.getCandles(s, '1h', { signal, limit: 24 })));
    return new Map(series.map((x) => [x.symbol, x.candles.map((c) => c.close)] as const));
  });

  // Re-run the analysis when a new candle opens (keeps the old one visible while refreshing).
  const lastTime = live.candles[live.candles.length - 1]?.time;
  const seenTime = useRef<number | undefined>(undefined);
  const reloaders = useRef([opportunity.reload, confluence.reload, watchSignals.reload]);
  reloaders.current = [opportunity.reload, confluence.reload, watchSignals.reload];
  useEffect(() => {
    if (lastTime === undefined) return;
    if (seenTime.current !== undefined && lastTime > seenTime.current) reloaders.current.forEach((reload) => reload());
    seenTime.current = lastTime;
  }, [lastTime]);
  useEffect(() => {
    seenTime.current = undefined;
  }, [ws.symbol, ws.timeframe]);

  const lastPrice = live.candles[live.candles.length - 1]?.close;
  const signalMap = useMemo(() => new Map<InstrumentSymbol, Opportunity>((watchSignals.data ?? []).map((o) => [o.symbol, o])), [watchSignals.data]);
  const sparks = sparkRes.data ?? new Map<InstrumentSymbol, number[]>();

  // Keyboard: 1/2/3 timeframe, [ ] previous/next instrument, Z zones, F forecast.
  const step = (delta: number) => {
    const i = INSTRUMENT_SYMBOLS.indexOf(ws.symbol);
    const next = INSTRUMENT_SYMBOLS[(i + delta + INSTRUMENT_SYMBOLS.length) % INSTRUMENT_SYMBOLS.length];
    if (next) updateWorkspace({ symbol: next });
  };
  const setTimeframe = (timeframe: Timeframe) => updateWorkspace({ timeframe });
  useHotkeys({
    '1': () => setTimeframe('15m'),
    '2': () => setTimeframe('1h'),
    '3': () => setTimeframe('4h'),
    '[': () => step(-1),
    ']': () => step(1),
    z: () => updateWorkspace({ showOpportunityOverlay: !ws.showOpportunityOverlay }),
    f: () => updateWorkspace({ showForecast: !ws.showForecast }),
  });
  const series = live.resource.data;

  let chartArea: React.ReactNode;
  if (live.resource.status === 'loading') {
    chartArea = (
      <Loading label={`Loading ${instrument.display} ${ws.timeframe} chart`}>
        <div className="flex h-full flex-col gap-3 p-4">
          <Skeleton className="h-4 w-64" />
          <Skeleton className="w-full flex-1" />
        </div>
      </Loading>
    );
  } else if (live.resource.status === 'error' && !series) {
    chartArea = !online ? (
      <OfflineState />
    ) : (
      <ErrorState error={live.resource.error} onRetry={live.resource.reload} title={`Could not load ${instrument.display} ${ws.timeframe} candles`} />
    );
  } else if (live.candles.length === 0) {
    chartArea = <EmptyState title="No price history" description={`No candles are available for ${instrument.display} on ${ws.timeframe}.`} />;
  } else {
    chartArea = (
      <PriceChart
        instrument={instrument}
        timeframe={ws.timeframe}
        candles={live.candles}
        chartType={ws.chartType}
        indicators={ws.indicators}
        opportunity={ws.showOpportunityOverlay ? (opportunity.data ?? null) : null}
        showForecast={ws.showForecast}
        timeZone={timeZone}
        theme={resolvedTheme}
        volumeKind={series?.volumeKind ?? 'tick'}
        provenance={series?.provenance ?? 'demo'}
      />
    );
  }

  // Exactly what the assistant may use: the data already on this screen.
  const assistantContext: AssistantContext = {
    symbol: ws.symbol,
    timeframe: ws.timeframe,
    lastPrice: lastPrice ?? null,
    priceProvenance: series?.provenance ?? null,
    feedStatus: live.feedStatus,
    opportunity: opportunity.data ?? null,
    confluence: confluence.data ?? [],
    riskProfile: shareRisk ? prefs.riskProfile : null,
  };

  const opportunityPanel = (
    <OpportunityPanel
      resource={opportunity}
      confluence={confluence}
      onSelectTimeframe={setTimeframe}
      instrument={instrument}
      timeframe={ws.timeframe}
      currentPrice={lastPrice}
      timeZone={timeZone}
      now={now}
      hideTitle={!wide}
      onAsk={() => setAskOpen(true)}
    />
  );
  const watchlist = (
    <Watchlist
      quotes={quotes}
      active={ws.symbol}
      onSelect={(symbol) => updateWorkspace({ symbol })}
      sparks={sparks}
      signals={signalMap}
      timeframe={ws.timeframe}
    />
  );

  return (
    <div className="flex flex-col lg:h-full">
      <InstrumentHeader
        instrument={instrument}
        candles={live.candles}
        quote={quotes.quotes.get(ws.symbol)}
        feedStatus={live.feedStatus}
        lastUpdateMs={live.lastUpdateMs}
        provenance={series?.provenance}
        timeZone={timeZone}
        now={now}
        loading={live.resource.status === 'loading'}
        timeframe={ws.timeframe}
        opportunity={opportunity.data}
        confluence={confluence.data}
      />
      {outsidePlan && demoPlan && (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-demo/40 bg-demo-soft px-4 py-2 text-xs text-fg">
          <span>
            <strong className="font-semibold">{getPlan(demoPlan.plan).name}</strong> (demo plan preview) covers gold only — {instrument.display} is included from Professional.
          </span>
          <button type="button" onClick={() => updateWorkspace({ symbol: 'XAUUSD' })} className="font-medium underline underline-offset-2">
            Switch to XAU/USD
          </button>
          <Link to="/membership#compare" className="text-fg-2 underline underline-offset-2">
            Compare plans
          </Link>
        </div>
      )}
      <ChartToolbar
        timeframe={ws.timeframe}
        chartType={ws.chartType}
        indicators={ws.indicators}
        showOverlay={ws.showOpportunityOverlay}
        showForecast={ws.showForecast}
        onTimeframe={setTimeframe}
        onChartType={(chartType) => updateWorkspace({ chartType })}
        onIndicators={(indicators) => updateWorkspace({ indicators })}
        onShowOverlay={(showOpportunityOverlay) => updateWorkspace({ showOpportunityOverlay })}
        onShowForecast={(showForecast) => updateWorkspace({ showForecast })}
      />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {wide && (
          <aside aria-label="Watchlist" className="w-[288px] shrink-0 border-r border-line bg-surface">
            <h2 className="flex h-11 items-center border-b border-line px-4 text-sm font-semibold text-fg">Watchlist</h2>
            <div className="h-[calc(100%-2.75rem)]">{watchlist}</div>
          </aside>
        )}

        <section aria-label="Price chart" className="relative h-[420px] min-w-0 bg-surface sm:h-[480px] lg:h-auto lg:flex-1">
          {chartArea}
        </section>

        <div className="flex min-h-0 flex-col border-t border-line lg:w-[340px] lg:shrink-0 lg:border-t-0 lg:border-l">
          {wide ? (
            opportunityPanel
          ) : (
            <>
              <div role="tablist" aria-label="Side panel" className="flex shrink-0 border-b border-line bg-surface">
                {(['opportunity', 'watchlist'] as const).map((tab) => (
                  <button
                    key={tab}
                    role="tab"
                    type="button"
                    id={`side-tab-${tab}`}
                    aria-selected={sideTab === tab}
                    aria-controls={`side-panel-${tab}`}
                    onClick={() => setSideTab(tab)}
                    className={cn(
                      'h-10 flex-1 border-b-2 text-sm font-medium',
                      sideTab === tab ? 'border-accent text-fg' : 'border-transparent text-fg-2 hover:text-fg',
                    )}
                  >
                    {tab === 'opportunity' ? 'AI opportunity' : 'Watchlist'}
                  </button>
                ))}
              </div>
              <div role="tabpanel" id={`side-panel-${sideTab}`} aria-labelledby={`side-tab-${sideTab}`} className="min-h-0 flex-1 lg:overflow-hidden">
                {sideTab === 'opportunity' ? opportunityPanel : <div className="h-[420px] bg-surface lg:h-full">{watchlist}</div>}
              </div>
            </>
          )}
        </div>
      </div>
      <SideSheet open={askOpen} onClose={() => setAskOpen(false)} title="Assistant" meta={<span className="text-xs text-fg-3">{instrument.display} · {ws.timeframe}</span>}>
        <AssistantPanel context={assistantContext} shareRisk={shareRisk} onShareRisk={setShareRisk} variant="drawer" timeZone={timeZone} />
      </SideSheet>
    </div>
  );
}
