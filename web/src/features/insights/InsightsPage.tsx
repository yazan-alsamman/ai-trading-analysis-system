import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, FlaskConical, RotateCw } from 'lucide-react';
import { useMemo, useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge, DemoBadge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox, Select } from '@/components/ui/Form';
import { ChangeText, DirectionBadge } from '@/components/ui/Market';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, Skeleton, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { getInstrument, INSTRUMENTS } from '@/domain/instruments';
import { computePredictionStats, OUTCOME_LABELS, predictionError, type PredictionOutcome, type PredictionRecord } from '@/domain/predictions';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatPercent, formatPercentChange, formatR } from '@/lib/format';
import { CalibrationChart } from './CalibrationChart';
import { PerformanceChart } from './PerformanceChart';

const PAGE_SIZE = 15;
const OUTCOME_TONE: Record<PredictionOutcome, BadgeTone> = { tp_hit: 'up', sl_hit: 'down', expired: 'neutral', open: 'forecast' };

function Kpi({ label, value, hint }: { label: string; value: React.ReactNode; hint: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <dt className="text-xs text-fg-3">{label}</dt>
      <dd className="num mt-1 text-xl leading-tight text-fg">{value}</dd>
      <dd className="mt-1 text-xs text-fg-3">{hint}</dd>
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome: PredictionOutcome }) {
  return <Badge tone={OUTCOME_TONE[outcome]}>{OUTCOME_LABELS[outcome]}</Badge>;
}

/** SF14 (general prediction statistics) and SF15 (per-prediction accuracy). */
export function InsightsPage() {
  usePageTitle('Insights');
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource('predictions', (signal) => services.predictions.listHistory({ signal }));
  const [symbol, setSymbol] = useState('all');
  const [outcome, setOutcome] = useState('all');
  const [mineOnly, setMineOnly] = useState(false);
  const [newestFirst, setNewestFirst] = useState(true);
  const [page, setPage] = useState(0);

  const records = useMemo(() => res.data ?? [], [res.data]);
  const isDemo = records[0]?.provenance === 'demo';
  const stats = useMemo(() => computePredictionStats(records), [records]);

  const byInstrument = useMemo(
    () =>
      INSTRUMENTS.map((i) => ({ instrument: i, stats: computePredictionStats(records.filter((r) => r.symbol === i.symbol)) })).filter((x) => x.stats.total > 0),
    [records],
  );

  const filtered = useMemo(() => {
    const list = records.filter(
      (r: PredictionRecord) => (symbol === 'all' || r.symbol === symbol) && (outcome === 'all' || r.outcome === outcome) && (!mineOnly || r.requestedByUser),
    );
    return newestFirst ? list : [...list].reverse();
  }, [records, symbol, outcome, mineOnly, newestFirst]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pageCount - 1);
  const visible = filtered.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);
  const setFilter = (fn: () => void) => {
    fn();
    setPage(0);
  };

  const gap = stats.hitRate !== null && stats.meanPredicted !== null ? stats.hitRate - stats.meanPredicted : null;

  return (
    <Page>
      <PageHeader
        title="Insights"
        meta={isDemo && <DemoBadge label="Demo statistics" />}
        description="How the AI's predictions have performed: overall statistics, calibration, and the outcome of every prediction."
        actions={
          <Button icon={RotateCw} onClick={res.reload} loading={res.isRefreshing} disabled={res.status === 'loading'}>
            Refresh
          </Button>
        }
      />

      {isDemo && (
        <div className="flex items-start gap-2.5 rounded-lg border border-demo/40 bg-demo-soft px-4 py-3 text-sm text-fg">
          <FlaskConical aria-hidden className="mt-0.5 size-4 shrink-0 text-demo" />
          <p>
            These figures are computed from <strong className="font-semibold">simulated predictions with random outcomes</strong>. They demonstrate the
            evaluation method only and say nothing about the accuracy of the project's real model.
          </p>
        </div>
      )}

      {res.status === 'loading' ? (
        <Loading label="Loading prediction statistics">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} title="Could not load prediction history" />
      ) : records.length === 0 ? (
        <EmptyState title="No predictions yet" description="Statistics appear once the AI has produced and resolved predictions." />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Kpi label="Predictions" value={formatNumber(stats.total)} hint={`${stats.resolved} resolved · ${stats.open} open`} />
            <Kpi label="Hit rate" value={formatPercent(stats.hitRate, 1)} hint="Target reached before stop" />
            <Kpi label="Mean predicted" value={formatPercent(stats.meanPredicted, 1)} hint="Average stated probability" />
            <Kpi
              label="Calibration gap"
              value={formatPercentChange(gap, 1)}
              hint={gap !== null && gap < 0 ? 'Model over-confident' : 'Model under-confident'}
            />
            <Kpi label="Brier score" value={formatNumber(stats.brierScore, 3)} hint="Lower is better · 0.250 = coin flip" />
          </dl>

          <Panel title="Performance" meta={<span>Realised result per prediction: target = +R:R, stop = −1R</span>}>
            <PerformanceChart records={records} timeZone={timeZone} />
          </Panel>

          <div className="grid gap-5 xl:grid-cols-[auto_minmax(0,1fr)]">
            <Panel title="Calibration" meta={<span>10-point bins</span>}>
              <div className="overflow-x-auto">
                <CalibrationChart bins={stats.calibration} />
              </div>
            </Panel>
            <Panel title="By instrument" flush>
              <TableRegion label="Statistics by instrument">
                <thead>
                  <tr>
                    <Th>Instrument</Th>
                    <Th numeric>Resolved</Th>
                    <Th numeric>Hit rate</Th>
                    <Th numeric>Mean predicted</Th>
                    <Th numeric>Mean result</Th>
                  </tr>
                </thead>
                <tbody>
                  {byInstrument.map(({ instrument, stats: s }) => (
                    <tr key={instrument.symbol}>
                      <Td className="font-medium">{instrument.display}</Td>
                      <Td numeric>{s.resolved}</Td>
                      <Td numeric>{formatPercent(s.hitRate, 1)}</Td>
                      <Td numeric>{formatPercent(s.meanPredicted, 1)}</Td>
                      <Td numeric>
                        <ChangeText value={s.meanRealizedR} text={formatR(s.meanRealizedR)} showIcon={false} />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </TableRegion>
            </Panel>
          </div>

          <Panel
            title="Prediction history"
            meta={<span aria-live="polite">{filtered.length} predictions</span>}
            flush
          >
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
                <Select aria-label="Filter by instrument" value={symbol} onChange={(e) => setFilter(() => setSymbol(e.target.value))} className="h-8 w-36">
                  <option value="all">All instruments</option>
                  {INSTRUMENTS.map((i) => (
                    <option key={i.symbol} value={i.symbol}>
                      {i.display}
                    </option>
                  ))}
                </Select>
                <Select aria-label="Filter by outcome" value={outcome} onChange={(e) => setFilter(() => setOutcome(e.target.value))} className="h-8 w-36">
                  <option value="all">All outcomes</option>
                  {Object.entries(OUTCOME_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </Select>
                <Checkbox label="Requested by me" checked={mineOnly} onChange={(e) => setFilter(() => setMineOnly(e.target.checked))} />
            </div>
            {filtered.length === 0 ? (
              <EmptyState title="No predictions match these filters" compact />
            ) : (
              <>
                <TableRegion label="Prediction history table">
                  <thead>
                    <tr>
                      <Th aria-sort={newestFirst ? 'descending' : 'ascending'} className="p-0">
                        <button type="button" onClick={() => setNewestFirst((v) => !v)} className="inline-flex h-9 items-center gap-1 px-3 text-fg hover:text-fg">
                          Generated {newestFirst ? <ArrowDown aria-hidden className="size-3.5" /> : <ArrowUp aria-hidden className="size-3.5" />}
                        </button>
                      </Th>
                      <Th>Instrument</Th>
                      <Th>TF</Th>
                      <Th>Direction</Th>
                      <Th numeric>Probability</Th>
                      <Th>Outcome</Th>
                      <Th numeric>Result</Th>
                      <Th numeric title="Squared error between the stated probability and the outcome (0 = perfect)">
                        Error
                      </Th>
                      <Th>Source</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((r) => (
                      <tr key={r.id} className="hover:bg-hover">
                        <Td className="num text-fg-2">{formatDateTime(r.generatedAt, timeZone)}</Td>
                        <Td className="font-medium">{getInstrument(r.symbol).display}</Td>
                        <Td className="text-fg-2">{r.timeframe}</Td>
                        <Td>
                          <DirectionBadge direction={r.direction} />
                        </Td>
                        <Td numeric className="text-forecast">
                          {formatPercent(r.probability)}
                        </Td>
                        <Td>
                          <OutcomeBadge outcome={r.outcome} />
                        </Td>
                        <Td numeric>{r.realizedR === undefined ? '—' : <ChangeText value={r.realizedR} text={formatR(r.realizedR)} showIcon={false} />}</Td>
                        <Td numeric className="text-fg-2">
                          {formatNumber(predictionError(r), 3)}
                        </Td>
                        <Td className="text-fg-2">{r.requestedByUser ? 'My request' : 'Automatic'}</Td>
                      </tr>
                    ))}
                  </tbody>
                </TableRegion>
                <nav aria-label="Pagination" className="flex items-center justify-between gap-3 px-4 py-2.5 text-xs text-fg-3">
                  <span className="num">
                    {current * PAGE_SIZE + 1}–{Math.min(filtered.length, (current + 1) * PAGE_SIZE)} of {filtered.length}
                  </span>
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" icon={ChevronLeft} disabled={current === 0} onClick={() => setPage(current - 1)}>
                      Previous
                    </Button>
                    <Button size="sm" variant="ghost" disabled={current >= pageCount - 1} onClick={() => setPage(current + 1)}>
                      Next <ChevronRight aria-hidden className="size-4" />
                    </Button>
                  </div>
                </nav>
              </>
            )}
          </Panel>
        </>
      )}
      {res.status === 'loading' && (
        <Loading label="Loading prediction history">
          <SkeletonRows rows={6} />
        </Loading>
      )}
    </Page>
  );
}
