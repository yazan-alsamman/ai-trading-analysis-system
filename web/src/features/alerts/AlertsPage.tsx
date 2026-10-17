import { BellPlus, Pause, Pencil, Play, RotateCcw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { appEvents } from '@/app/events';
import { Badge, DemoBadge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { CHANNEL_LABELS, CONDITION_LABELS, type PriceAlert, type PriceAlertDraft } from '@/domain/alerts';
import { getInstrument, type InstrumentSymbol } from '@/domain/instruments';
import { useLiveQuotes } from '@/hooks/useMarketData';
import { useHashScroll } from '@/hooks/useHashScroll';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatPips, formatPrice } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { OpportunityNotifications } from './OpportunityNotifications';
import { PriceAlertDialog } from './PriceAlertDialog';

const STATUS_TONE = { active: 'accent', paused: 'neutral', triggered: 'info' } as const;
const STATUS_LABEL = { active: 'Active', paused: 'Paused', triggered: 'Triggered' } as const;

export function AlertsPage() {
  usePageTitle('Alerts');
  useHashScroll();
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const quotes = useLiveQuotes();
  const alerts = useResource('alerts', (signal) => services.alerts.list({ signal }));
  const [editing, setEditing] = useState<PriceAlert | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<PriceAlert | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Stay in sync with the alert monitor (an alert may fire while this page is open).
  const reloadAlerts = alerts.reload;
  useEffect(() => appEvents.on('alerts-changed', reloadAlerts), [reloadAlerts]);

  const quoteMap = quotes.quotes;
  const currentPrice = useCallback((symbol: InstrumentSymbol) => quoteMap.get(symbol)?.price, [quoteMap]);
  const isDemo = services.source === 'demo';

  const save = async (draft: PriceAlertDraft) => {
    if (editing) {
      const updated = await services.alerts.update(editing.id, draft);
      alerts.setData((list) => (list ?? []).map((a) => (a.id === updated.id ? updated : a)));
      notify('Alert updated.', 'success');
      appEvents.emit('alerts-changed');
    } else {
      const created = await services.alerts.create(draft);
      alerts.setData((list) => [created, ...(list ?? [])]);
      notify(`Alert created for ${getInstrument(created.symbol).display}.`, 'success');
      appEvents.emit('alerts-changed');
    }
  };

  const toggleStatus = async (alert: PriceAlert) => {
    setBusyId(alert.id);
    try {
      const updated = await services.alerts.update(alert.id, { status: alert.status === 'active' ? 'paused' : 'active' });
      alerts.setData((list) => (list ?? []).map((a) => (a.id === updated.id ? updated : a)));
      appEvents.emit('alerts-changed');
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setBusyId(deleting.id);
    try {
      await services.alerts.remove(deleting.id);
      alerts.setData((list) => (list ?? []).filter((a) => a.id !== deleting.id));
      notify('Alert deleted.', 'info');
      appEvents.emit('alerts-changed');
      setDeleting(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const openNew = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  return (
    <Page width="reading">
      <PageHeader
        title="Alerts"
        meta={isDemo && <DemoBadge label="Stored locally" detail="Demo: alerts are kept in this browser. Delivery needs the backend notification service." />}
        description="Get notified when a pair reaches a price level, or when the AI detects an opportunity matching your criteria. Alerts notify only — they never open or close trades."
        actions={
          <Button variant="primary" icon={BellPlus} onClick={openNew}>
            New price alert
          </Button>
        }
      />

      <Panel title="Price alerts" meta={alerts.data && <span>{alerts.data.length} total</span>} flush>
        {alerts.status === 'loading' ? (
          <Loading label="Loading alerts">
            <SkeletonRows rows={3} className="p-4" />
          </Loading>
        ) : alerts.status === 'error' && !alerts.data ? (
          <ErrorState error={alerts.error} onRetry={alerts.reload} compact />
        ) : (alerts.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="No price alerts yet"
            description="Create an alert to be notified when a pair crosses a level you choose."
            action={
              <Button size="sm" icon={BellPlus} onClick={openNew}>
                New price alert
              </Button>
            }
          />
        ) : (
          <TableRegion label="Price alerts table">
            <thead>
              <tr>
                <Th>Instrument</Th>
                <Th>Condition</Th>
                <Th numeric>Level</Th>
                <Th numeric>Current</Th>
                <Th numeric>Distance</Th>
                <Th>Channels</Th>
                <Th>Status</Th>
                <Th>Created</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {(alerts.data ?? []).map((a) => {
                const inst = getInstrument(a.symbol);
                const price = currentPrice(a.symbol);
                return (
                  <tr key={a.id} className="hover:bg-hover">
                    <Td className="font-medium">
                      {inst.display}
                      {a.note && <span className="block max-w-56 truncate text-xs font-normal text-fg-3">{a.note}</span>}
                    </Td>
                    <Td className="text-fg-2">{CONDITION_LABELS[a.condition]}</Td>
                    <Td numeric>{formatPrice(a.price, inst.pricePrecision)}</Td>
                    <Td numeric className="text-fg-2">
                      {formatPrice(price, inst.pricePrecision)}
                    </Td>
                    <Td numeric className="text-fg-2">
                      {price === undefined ? '—' : formatPips(a.price - price, inst.pipSize)}
                    </Td>
                    <Td className="text-fg-2">{services.source === 'api' ? 'Your notification settings' : a.channels.map((c) => CHANNEL_LABELS[c]).join(', ')}</Td>
                    <Td>
                      <Badge tone={STATUS_TONE[a.status]}>{STATUS_LABEL[a.status]}</Badge>
                    </Td>
                    <Td className="num text-fg-2">{formatDate(a.createdAt, timeZone)}</Td>
                    <Td>
                      <div className="flex justify-end gap-0.5">
                        <IconButton
                          icon={a.status === 'active' ? Pause : a.status === 'triggered' ? RotateCcw : Play}
                          label={
                            a.status === 'active'
                              ? `Pause alert for ${inst.display}`
                              : a.status === 'triggered'
                                ? `Re-arm alert for ${inst.display}`
                                : `Resume alert for ${inst.display}`
                          }
                          size="sm"
                          disabled={busyId === a.id}
                          onClick={() => toggleStatus(a)}
                          tooltipSide="left"
                        />
                        <IconButton
                          icon={Pencil}
                          disabled={a.condition !== 'crosses_above' && a.condition !== 'crosses_below'}
                          label={a.condition === 'crosses_above' || a.condition === 'crosses_below' ? `Edit alert for ${inst.display}` : `This alert type is edited in the app that created it`}
                          size="sm"
                          onClick={() => {
                            setEditing(a);
                            setDialogOpen(true);
                          }}
                          tooltipSide="left"
                        />
                        <IconButton icon={Trash2} label={`Delete alert for ${inst.display}`} size="sm" onClick={() => setDeleting(a)} tooltipSide="left" />
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </TableRegion>
        )}
      </Panel>

      <OpportunityNotifications />

      <PriceAlertDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        alert={editing}
        currentPrice={currentPrice}
        onSubmit={save}
        provenanceLabel={isDemo ? 'simulated' : null}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete price alert?"
        description={
          deleting
            ? `The alert for ${getInstrument(deleting.symbol).display} ${CONDITION_LABELS[deleting.condition].toLowerCase()} ${formatPrice(deleting.price, getInstrument(deleting.symbol).pricePrecision)} will be removed. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete alert"
        busy={busyId !== null && busyId === deleting?.id}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </Page>
  );
}
