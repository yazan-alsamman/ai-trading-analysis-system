import { useEffect } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { appEvents } from '@/app/events';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatPct, MISSING } from '@/lib/format';

const CONDITION_TEXT: Record<string, string> = {
  crosses_above: 'Crosses above',
  crosses_below: 'Crosses below',
  above: 'Above',
  below: 'Below',
  change_pct: 'Changes by %',
};

/** Backend mode: price alerts that fired on the server (GET /me/price-alerts/history). */
export function AlertHistoryPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const history = useResource('alert-history', (signal) => services.alerts.history({ limit: 50 }, { signal }));

  const reload = history.reload;
  useEffect(() => appEvents.on('alerts-changed', reload), [reload]);

  return (
    <div id="history" className="scroll-mt-4">
      <Panel title="Trigger history" meta={<span>Alerts that fired on the server, newest first</span>} flush>
        {history.status === 'loading' ? (
          <Loading label="Loading alert history">
            <SkeletonRows rows={3} className="p-4" />
          </Loading>
        ) : history.status === 'error' && !history.data ? (
          <ErrorState error={history.error} onRetry={history.reload} compact />
        ) : (history.data?.length ?? 0) === 0 ? (
          <EmptyState compact title="No alert has fired yet" description="When the price reaches one of your alert levels, the trigger is recorded here." />
        ) : (
          <TableRegion label="Alert trigger history">
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>Instrument</Th>
                <Th>Condition</Th>
                <Th numeric>Level</Th>
                <Th numeric>Price</Th>
                <Th numeric>Change</Th>
                <Th>Note</Th>
              </tr>
            </thead>
            <tbody>
              {(history.data ?? []).map((t) => (
                <tr key={t.notificationId} className="hover:bg-hover">
                  <Td className="num text-fg-2">{formatDateTime(t.barTime ?? t.createdAt, timeZone)}</Td>
                  <Td className="font-medium">{t.symbol ?? MISSING}</Td>
                  <Td className="text-fg-2">{t.condition ? (CONDITION_TEXT[t.condition] ?? t.condition) : MISSING}</Td>
                  <Td numeric>{t.condition === 'change_pct' ? formatPct(t.value) : formatNumber(t.value, 5).replace(/\.?0+$/, '')}</Td>
                  <Td numeric>{formatNumber(t.price, 5).replace(/\.?0+$/, '')}</Td>
                  <Td numeric className="text-fg-2">
                    {formatPct(t.changePct)}
                  </Td>
                  <Td className="max-w-56 truncate text-fg-2">{t.note ?? ''}</Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
        )}
      </Panel>
    </div>
  );
}
