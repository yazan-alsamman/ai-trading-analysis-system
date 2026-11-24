import { useMemo } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Dialog } from '@/components/ui/Dialog';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { METRIC_LABELS, metricNumber, type BacktestComparison } from '@/domain/backtests';
import { SeriesChart, type SeriesLine } from '@/features/chart/SeriesChart';
import { useResource } from '@/hooks/useResource';
import { formatMetric, formatWindow } from './backtestFormat';
import { BacktestDisclaimer } from './backtestParts';

/** Currency-free metrics: compared backtests can be on instruments with different quote currencies. */
const COMPARE_KEYS = [
  'total_return_pct',
  'buy_and_hold_return_pct',
  'cagr_pct',
  'max_drawdown_pct',
  'sharpe',
  'sortino',
  'calmar',
  'profit_factor',
  'trades',
  'win_rate_pct',
  'exposure_pct',
  'max_consecutive_losses',
];
const COMPARE_METRICS = METRIC_LABELS.filter((m) => COMPARE_KEYS.includes(m.key));

function CompareBody({ ids, label }: { ids: string[]; label: (key: string) => string }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource(`backtest-compare:${ids.join(',')}`, () => services.backtests.compare(ids));
  const items: BacktestComparison['items'] = useMemo(() => res.data?.items ?? [], [res.data]);
  const lines = useMemo<SeriesLine[]>(
    () => items.map((it, i) => ({ name: `#${i + 1} ${label(it.strategyKey)}`, points: it.equity, pane: 0 })),
    [items, label],
  );

  if (res.status === 'loading')
    return (
      <Loading label="Comparing backtests">
        <SkeletonRows rows={6} />
      </Loading>
    );
  if (res.status === 'error' && !res.data) return <ErrorState error={res.error} onRetry={res.reload} title="Could not compare these backtests" compact />;

  return (
    <div className="flex flex-col gap-4">
      <SeriesChart label={`Equity of ${items.length} backtests, normalised to 100 at each start`} lines={lines} height={260} />
      <TableRegion label="Metrics side by side">
        <thead>
          <tr>
            <Th>Metric</Th>
            {items.map((it, i) => (
              <Th key={it.id} numeric>
                #{i + 1}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <Td className="text-fg-3">Strategy</Td>
            {items.map((it) => (
              <Td key={it.id} className="text-right">
                {label(it.strategyKey)}
              </Td>
            ))}
          </tr>
          <tr>
            <Td className="text-fg-3">Instrument</Td>
            {items.map((it) => (
              <Td key={it.id} className="text-right">
                {it.instrument.symbol} · {it.timeframe}
              </Td>
            ))}
          </tr>
          <tr>
            <Td className="text-fg-3">Window</Td>
            {items.map((it) => (
              <Td key={it.id} className="text-right text-fg-2">
                {formatWindow(it.start, it.end, timeZone)}
              </Td>
            ))}
          </tr>
          {COMPARE_METRICS.map((m) => (
            <tr key={m.key}>
              <Td className="text-fg-3" title={m.hint}>
                {m.label}
              </Td>
              {items.map((it) => (
                <Td key={it.id} numeric>
                  {formatMetric(m.kind, metricNumber(it.metrics, m.key), 'USD')}
                </Td>
              ))}
            </tr>
          ))}
        </tbody>
      </TableRegion>
      <BacktestDisclaimer />
    </div>
  );
}

/** POST /backtests/compare: metrics side by side and equity normalised to 100. */
export function CompareDialog({ ids, open, onClose, label }: { ids: string[]; open: boolean; onClose: () => void; label: (key: string) => string }) {
  return (
    <Dialog open={open} onClose={onClose} title="Compare backtests" description="Completed backtests side by side. Equity curves start at 100." size="lg">
      <CompareBody ids={ids} label={label} />
    </Dialog>
  );
}
