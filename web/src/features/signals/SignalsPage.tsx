import { ArrowUpRight, BellRing, FilterX, RotateCw } from 'lucide-react';
import { useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge, DemoBadge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Checkbox, Select } from '@/components/ui/Form';
import { DirectionBadge } from '@/components/ui/Market';
import { Page, PageHeader } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { SortableTh, TableRegion, Td, Th } from '@/components/ui/Table';
import { getInstrument, INSTRUMENTS, isInstrumentSymbol } from '@/domain/instruments';
import { isTimeframe, TIMEFRAMES } from '@/domain/market';
import { isOpportunityStale, RISK_LABELS, SETUP_LABELS, type Opportunity } from '@/domain/opportunity';
import { useNow } from '@/hooks/useEnvironment';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { nextSort, type SortState } from '@/lib/sort';
import { formatDateTime, formatPercent, formatPrice, formatProbabilityBand, formatR, formatRelative, formatRiskReward } from '@/lib/format';
import { ProbabilityMeter } from '../opportunity/ProbabilityMeter';
import { SignalSummary } from './SignalSummary';

type SortKey = 'symbol' | 'probability' | 'ev' | 'generated';

const MIN_PROBABILITY_OPTIONS = [0, 0.55, 0.6, 0.65, 0.7, 0.75];

/** Filters live in the URL: they survive navigation and can be shared. */
function useSignalFilters() {
  const [params, setParams] = useSearchParams();
  const symbol = params.get('symbol') ?? 'all';
  const timeframe = params.get('tf') ?? 'all';
  const direction = params.get('dir') ?? 'all';
  const minProbability = Number(params.get('min') ?? 0);
  const includeNone = params.get('none') === '1';
  const sortKey = (params.get('sort') as SortKey | null) ?? 'probability';
  const sortDir = params.get('order') === 'asc' ? 'asc' : 'desc';

  const set = (patch: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v === null || v === 'all' || v === '0') next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );

  return {
    symbol: symbol === 'all' || isInstrumentSymbol(symbol) ? symbol : 'all',
    timeframe: timeframe === 'all' || isTimeframe(timeframe) ? timeframe : 'all',
    direction: ['all', 'long', 'short'].includes(direction) ? direction : 'all',
    minProbability: Number.isFinite(minProbability) ? minProbability : 0,
    includeNone,
    sort: { key: (['symbol', 'probability', 'ev', 'generated'] as const).includes(sortKey) ? sortKey : 'probability', direction: sortDir } as SortState<SortKey>,
    set,
    active: params.toString() !== '' && [...params.keys()].some((k) => k !== 'sort' && k !== 'order'),
    reset: () => setParams(new URLSearchParams(), { replace: true }),
  };
}

function compare(a: Opportunity, b: Opportunity, key: SortKey): number {
  switch (key) {
    case 'symbol':
      return a.symbol.localeCompare(b.symbol) || a.timeframe.localeCompare(b.timeframe);
    case 'probability':
      return a.probability - b.probability;
    case 'ev':
      return (a.expectedValueR ?? -Infinity) - (b.expectedValueR ?? -Infinity);
    case 'generated':
      return a.generatedAt - b.generatedAt;
  }
}

export function SignalsPage() {
  usePageTitle('Signals');
  const services = useServices();
  const { timeZone, updateWorkspace } = usePreferences();
  const navigate = useNavigate();
  const now = useNow(15_000);
  const f = useSignalFilters();
  const res = useResource('opportunities:all', (signal) => services.opportunities.list({}, { signal }));

  const rows = useMemo(() => {
    const all = res.data ?? [];
    const filtered = all.filter(
      (o) =>
        (f.includeNone || o.status === 'detected') &&
        (f.symbol === 'all' || o.symbol === f.symbol) &&
        (f.timeframe === 'all' || o.timeframe === f.timeframe) &&
        (f.direction === 'all' || o.direction === f.direction) &&
        (o.status !== 'detected' || o.probability >= f.minProbability),
    );
    const dir = f.sort.direction === 'asc' ? 1 : -1;
    return [...filtered].sort((a, b) => compare(a, b, f.sort.key) * dir);
  }, [res.data, f.includeNone, f.symbol, f.timeframe, f.direction, f.minProbability, f.sort.key, f.sort.direction]);

  const detectedCount = res.data?.filter((o) => o.status === 'detected').length ?? 0;
  const onSort = (key: SortKey) => {
    const next = nextSort(f.sort, key, key === 'symbol' ? 'asc' : 'desc');
    f.set({ sort: next.key, order: next.direction });
  };

  const open = (o: Opportunity) => {
    updateWorkspace({ symbol: o.symbol, timeframe: o.timeframe, showOpportunityOverlay: true });
    navigate('/workspace');
  };

  return (
    <Page>
      <PageHeader
        title="Signals"
        meta={res.data?.[0]?.provenance === 'demo' && <DemoBadge />}
        description="Latest AI opportunity analysis for every supported instrument and timeframe. Probabilities are estimates that the take-profit is reached before the stop-loss — not guarantees."
        actions={
          <>
            <Link
              to="/alerts#opportunity-notifications"
              className="inline-flex h-9 items-center gap-2 rounded-md border border-line-strong px-3.5 text-sm font-medium text-fg hover:bg-hover"
            >
              <BellRing aria-hidden className="size-4" /> Notify me
            </Link>
            <Button icon={RotateCw} onClick={res.reload} loading={res.isRefreshing} disabled={res.status === 'loading'}>
              Refresh
            </Button>
          </>
        }
      />

      {res.data && res.data.length > 0 && <SignalSummary items={res.data} />}

      <section aria-label="Signal list" className="rounded-lg border border-line bg-surface">
        <div className="flex flex-wrap items-end gap-3 border-b border-line p-3">
          <label className="flex flex-col gap-1 text-xs text-fg-3">
            Instrument
            <Select value={f.symbol} onChange={(e) => f.set({ symbol: e.target.value })} className="w-36">
              <option value="all">All instruments</option>
              {INSTRUMENTS.map((i) => (
                <option key={i.symbol} value={i.symbol}>
                  {i.display}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-3">
            Timeframe
            <Select value={f.timeframe} onChange={(e) => f.set({ tf: e.target.value })} className="w-28">
              <option value="all">All</option>
              {TIMEFRAMES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-3">
            Direction
            <Select value={f.direction} onChange={(e) => f.set({ dir: e.target.value })} className="w-28">
              <option value="all">All</option>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-3">
            Min. probability
            <Select value={String(f.minProbability)} onChange={(e) => f.set({ min: e.target.value })} className="w-28">
              {MIN_PROBABILITY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p === 0 ? 'Any' : `≥ ${formatPercent(p)}`}
                </option>
              ))}
            </Select>
          </label>
          <Checkbox
            className="pb-2"
            label="Include “no opportunity”"
            checked={f.includeNone}
            onChange={(e) => f.set({ none: e.target.checked ? '1' : null })}
          />
          <div className="ml-auto flex items-center gap-3 pb-1.5">
            <p className="text-xs text-fg-3" aria-live="polite">
              {res.status === 'success' && `${rows.length} shown · ${detectedCount} detected of ${res.data?.length ?? 0} analyses`}
            </p>
            {f.active && (
              <Button size="sm" variant="ghost" icon={FilterX} onClick={f.reset}>
                Clear filters
              </Button>
            )}
          </div>
        </div>

        {res.status === 'loading' ? (
          <Loading label="Loading signals">
            <SkeletonRows rows={8} className="p-3" />
          </Loading>
        ) : res.status === 'error' && !res.data ? (
          <ErrorState error={res.error} onRetry={res.reload} title="Could not load signals" />
        ) : (res.data?.length ?? 0) === 0 ? (
          <EmptyState title="No analyses available" description="The AI service returned no analyses. Try again later." />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No signals match these filters"
            description="Lower the minimum probability or include instruments without an opportunity."
            action={
              <Button size="sm" icon={FilterX} onClick={f.reset}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <TableRegion label="Signals table">
            <thead>
              <tr>
                <SortableTh sortKey="symbol" sort={f.sort} onSort={onSort}>
                  Instrument
                </SortableTh>
                <Th>TF</Th>
                <Th>Signal</Th>
                <SortableTh sortKey="probability" sort={f.sort} onSort={onSort} numeric>
                  Probability
                </SortableTh>
                <Th numeric>Band</Th>
                <Th numeric>Entry zone</Th>
                <Th numeric>R : R</Th>
                <SortableTh sortKey="ev" sort={f.sort} onSort={onSort} numeric>
                  EV
                </SortableTh>
                <Th>Setup</Th>
                <Th>Risk</Th>
                <SortableTh sortKey="generated" sort={f.sort} onSort={onSort}>
                  Generated
                </SortableTh>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => {
                const inst = getInstrument(o.symbol);
                const detected = o.status === 'detected';
                const stale = isOpportunityStale(o, now);
                return (
                  <tr key={o.id} className="hover:bg-hover">
                    <Td className="font-medium">{inst.display}</Td>
                    <Td className="text-fg-2">{o.timeframe}</Td>
                    <Td>{detected ? <DirectionBadge direction={o.direction} /> : <Badge>No opportunity</Badge>}</Td>
                    <Td numeric>
                      {detected ? (
                        <div className="flex items-center justify-end gap-2">
                          <ProbabilityMeter probability={o.probability} band={o.confidenceBand} size="sm" className="w-16" />
                          <span className="w-10 text-forecast">{formatPercent(o.probability)}</span>
                        </div>
                      ) : (
                        <span className="text-fg-3">—</span>
                      )}
                    </Td>
                    <Td numeric className="text-fg-2">
                      {detected ? formatProbabilityBand(o.confidenceBand) : '—'}
                    </Td>
                    <Td numeric>{detected ? `${formatPrice(o.entryZone.low, inst.pricePrecision)}–${formatPrice(o.entryZone.high, inst.pricePrecision)}` : '—'}</Td>
                    <Td numeric>{detected ? formatRiskReward(o.riskReward) : '—'}</Td>
                    <Td numeric>{detected ? formatR(o.expectedValueR) : '—'}</Td>
                    <Td className="text-fg-2">{detected ? SETUP_LABELS[o.setupType] : '—'}</Td>
                    <Td className="text-fg-2">{detected ? RISK_LABELS[o.riskLevel] : '—'}</Td>
                    <Td className="text-fg-2">
                      <span className="num" title={formatDateTime(o.generatedAt, timeZone)}>
                        {formatRelative(o.generatedAt, now)}
                      </span>
                      {stale && (
                        <Badge tone="warning" className="ml-2" title="Older than its validity window">
                          Stale
                        </Badge>
                      )}
                    </Td>
                    <Td className="text-right">
                      <IconButton icon={ArrowUpRight} size="sm" label={`Open ${inst.display} ${o.timeframe} in workspace`} onClick={() => open(o)} tooltipSide="left" />
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </TableRegion>
        )}
      </section>
    </Page>
  );
}
