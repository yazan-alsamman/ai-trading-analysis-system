import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { strategyLabel, type BackendInstrument, type CustomStrategySummary, type StrategyDefinition } from '@/domain/strategies';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatPercent, formatPrice } from '@/lib/format';
import { formatJsonValue, humanize, instrumentLabel } from './strategyUtils';

/** One level of nesting flattened to `parent · child`, so any plan shape the risk engine sends stays readable. */
function planEntries(plan: Record<string, unknown>): [string, string][] {
  return Object.entries(plan).flatMap(([k, v]): [string, string][] =>
    v !== null && typeof v === 'object' && !Array.isArray(v)
      ? Object.entries(v as Record<string, unknown>).map(([k2, v2]): [string, string] => [`${humanize(k)} · ${humanize(k2)}`, formatJsonValue(v2)])
      : [[humanize(k), formatJsonValue(v)]],
  );
}

/** GET /me/signal-plans: the server's trade plan for each live signal of your activations. */
export function SignalPlansSection({
  catalog,
  custom,
  instruments,
}: {
  catalog: readonly StrategyDefinition[];
  custom: readonly CustomStrategySummary[];
  instruments: readonly BackendInstrument[] | undefined;
}) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource('signal-plans', (signal) => services.strategies.signalPlans({ limit: 50 }, { signal }));

  return (
    <Panel
      title="Signal plans"
      meta={<span>Plans computed by the server's risk engine for your strategies' signals. Information only: the platform never places trades.</span>}
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading signal plans">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title="No signal plans yet" description="When one of your active strategies signals, the server records a plan for it here." />
      ) : (
        <ul className="divide-y divide-line">
          {res.data.map((p) => {
            const precision = instruments?.find((i) => i.id === p.signal.instrumentId)?.pricePrecision ?? 5;
            const entries = planEntries(p.plan);
            return (
              <li key={p.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge tone={p.signal.side === 'buy' ? 'up' : 'down'}>{p.signal.side === 'buy' ? 'Buy' : 'Sell'}</Badge>
                  <span className="font-medium text-fg">{instrumentLabel(p.signal.instrumentId, instruments)}</span>
                  <span className="text-fg-2">
                    {p.signal.timeframe} · {strategyLabel(p.signal.strategyKey, catalog, custom)}
                  </span>
                  <span className="num ml-auto text-xs text-fg-3">{formatDateTime(p.signal.time * 1000, timeZone)}</span>
                </div>
                <p className="mt-1 text-xs text-fg-3">
                  Signal price <span className="num text-fg-2">{formatPrice(p.signal.price, precision)}</span> · strength{' '}
                  <span className="num text-fg-2">{formatPercent(p.signal.strength)}</span> · {humanize(p.signal.reason)}
                </p>
                {entries.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs font-medium text-fg-2">Server plan ({entries.length} fields)</summary>
                    <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
                      {entries.map(([k, v]) => (
                        <div key={k} className="flex min-w-0 justify-between gap-3">
                          <dt className="text-fg-3">{k}</dt>
                          <dd className="num truncate text-fg" title={v}>
                            {v}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
