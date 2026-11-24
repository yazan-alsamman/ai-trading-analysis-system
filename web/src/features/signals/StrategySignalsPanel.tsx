import { ArrowDownRight, ArrowUpRight, RotateCw } from 'lucide-react';
import { usePreferences, useServices } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { getInstrument } from '@/domain/instruments';
import { reasonText, strategyName } from '@/domain/strategySignals';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatDateTime, formatPrice } from '@/lib/format';

/**
 * Backend mode: the latest signals of the backend's rule-based strategy engine
 * (GET /api/v1/signals). They are shown as what they are — a rule fired on a
 * bar — and never presented as the AI model's probabilities or zones.
 */
export function StrategySignalsPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource('strategy-signals', (signal) => services.strategySignals.list({ limit: 50 }, { signal }));

  return (
    <Panel
      title="Strategy-engine signals"
      actions={
        <>
          <SourceTag kind="live" />
          <Button size="sm" icon={RotateCw} onClick={res.reload} loading={res.isRefreshing} disabled={res.status === 'loading'} aria-label="Refresh strategy signals" />
        </>
      }
    >
      <p className="mb-3 text-xs text-fg-3">
        Rule-based signals from the backend (RSI reversal, moving-average crossover, …): a rule fired on a closed bar. They carry no probability, entry zone or
        target, and are not the AI model’s output.
      </p>
      {res.status === 'loading' ? (
        <Loading label="Loading strategy signals">
          <SkeletonRows rows={4} />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} title="Could not load strategy signals" compact />
      ) : !res.data?.length ? (
        <EmptyState title="No strategy signals yet" description="Signals appear when an activated strategy fires on a closed bar." compact />
      ) : (
        <TableRegion label="Strategy signals">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <Th>Bar time</Th>
                <Th>Instrument</Th>
                <Th>Strategy</Th>
                <Th>Side</Th>
                <Th numeric>Price</Th>
                <Th>Reason</Th>
              </tr>
            </thead>
            <tbody>
              {res.data.map((s) => {
                const precision = s.symbol ? getInstrument(s.symbol).pricePrecision : 2;
                const buy = s.side === 'buy';
                return (
                  <tr key={s.id}>
                    <Td className="num whitespace-nowrap text-fg-2">{formatDateTime(s.time * 1000, timeZone)}</Td>
                    <Td className="whitespace-nowrap">
                      <span className="text-fg">{s.symbol ? getInstrument(s.symbol).display : s.instrumentLabel}</span>
                      <span className="num ml-1.5 text-xs text-fg-3">{s.timeframe}</span>
                    </Td>
                    <Td className="text-fg-2">{strategyName(s.strategyKey)}</Td>
                    <Td>
                      <span className={cn('inline-flex items-center gap-1 text-xs font-medium', buy ? 'text-up' : 'text-down')}>
                        {buy ? <ArrowUpRight aria-hidden className="size-3.5" /> : <ArrowDownRight aria-hidden className="size-3.5" />}
                        {buy ? 'Buy' : 'Sell'}
                      </span>
                    </Td>
                    <Td numeric className="num">
                      {formatPrice(s.price, precision)}
                    </Td>
                    <Td className="text-xs text-fg-2">{reasonText(s.reason)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableRegion>
      )}
    </Panel>
  );
}
