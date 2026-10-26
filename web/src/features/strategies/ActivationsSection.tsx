import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Switch } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { strategyLabel, type BackendInstrument, type CustomStrategySummary, type StrategyActivation, type StrategyDefinition } from '@/domain/strategies';
import type { Resource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { errorText, formatJsonValue, instrumentLabel } from './strategyUtils';

interface Props {
  activations: Resource<StrategyActivation[]>;
  catalog: readonly StrategyDefinition[];
  custom: readonly CustomStrategySummary[];
  instruments: readonly BackendInstrument[] | undefined;
  onActivate: () => void;
}

/** The user's activations (GET /me/strategies): what the live signal engine evaluates for them. */
export function ActivationsSection({ activations, catalog, custom, instruments, onActivate }: Props) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<StrategyActivation | null>(null);

  const patch = async (a: StrategyActivation, change: { isActive?: boolean; notify?: boolean }) => {
    setBusyId(a.id);
    try {
      const updated = await services.strategies.updateActivation(a.id, change);
      activations.setData((list) => (list ?? []).map((x) => (x.id === updated.id ? updated : x)));
    } catch (e) {
      notify(errorText(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusyId(deleting.id);
    try {
      await services.strategies.removeActivation(deleting.id);
      activations.setData((list) => (list ?? []).filter((x) => x.id !== deleting.id));
      notify('Strategy deactivated and removed.', 'info');
      setDeleting(null);
    } catch (e) {
      notify(errorText(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Panel
      title="My strategies"
      meta={activations.data && <span>{activations.data.filter((a) => a.isActive).length} running</span>}
      actions={
        <Button size="sm" variant="primary" icon={Plus} onClick={onActivate}>
          Activate strategy
        </Button>
      }
      flush
    >
      {activations.status === 'loading' ? (
        <Loading label="Loading your strategies">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : activations.status === 'error' && !activations.data ? (
        <ErrorState error={activations.error} onRetry={activations.reload} compact />
      ) : !activations.data?.length ? (
        <EmptyState
          title="No active strategies"
          description="Activate a platform or custom strategy on an instrument. The server checks it on every closed bar and records signals for you."
          action={
            <Button size="sm" icon={Plus} onClick={onActivate}>
              Activate strategy
            </Button>
          }
        />
      ) : (
        <ul className="divide-y divide-line">
          {activations.data.map((a) => {
            const label = strategyLabel(a.strategyKey, catalog, custom);
            const params = Object.entries(a.params);
            return (
              <li key={a.id} className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                    {a.name ?? label}
                    {a.strategyKey.startsWith('custom:') && <Badge tone="accent">Custom</Badge>}
                    {!a.isActive && <Badge>Paused</Badge>}
                  </p>
                  <p className="text-xs text-fg-3">
                    {a.name ? `${label} · ` : ''}
                    {instrumentLabel(a.instrumentId, instruments)} · {a.timeframe} · since {formatDate(a.createdAt, timeZone)}
                  </p>
                  {params.length > 0 && (
                    <p className="num mt-0.5 truncate text-xs text-fg-3" title={params.map(([k, v]) => `${k}=${formatJsonValue(v)}`).join(', ')}>
                      {params.map(([k, v]) => `${k}=${formatJsonValue(v)}`).join(' · ')}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-5">
                  <div className="w-28">
                    <Switch checked={a.isActive} disabled={busyId === a.id} onChange={(v) => void patch(a, { isActive: v })} label="Running" />
                  </div>
                  <div className="w-24">
                    <Switch checked={a.notify} disabled={busyId === a.id} onChange={(v) => void patch(a, { notify: v })} label="Notify" />
                  </div>
                  <IconButton icon={Trash2} label={`Remove ${a.name ?? label}`} size="sm" disabled={busyId === a.id} onClick={() => setDeleting(a)} tooltipSide="left" />
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <ConfirmDialog
        open={deleting !== null}
        title="Remove this strategy?"
        description="The server stops evaluating it for you and no new signals are recorded from it."
        confirmLabel="Remove"
        busy={busyId !== null && busyId === deleting?.id}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
