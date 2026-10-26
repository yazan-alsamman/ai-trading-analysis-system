import { Copy, Globe, LineChart, Lock, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { CustomStrategy, CustomStrategySummary } from '@/domain/strategies';
import type { Resource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { CustomStrategyDialog, type CustomEditTarget } from './CustomStrategyDialog';
import { errorText } from './strategyUtils';

const toSummary = (s: CustomStrategy): CustomStrategySummary => ({
  id: s.id,
  key: s.key,
  name: s.name,
  description: s.description,
  kind: s.kind,
  visibility: s.visibility,
  version: s.version,
  clonedFrom: s.clonedFrom,
  createdAt: s.createdAt,
  updatedAt: s.updatedAt,
});

/** The user's builder and composite strategies (/me/custom-strategies). */
export function CustomSection({ custom, onPreview }: { custom: Resource<CustomStrategySummary[]>; onPreview: (s: CustomStrategySummary) => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [editing, setEditing] = useState<CustomEditTarget | null>(null);
  const [session, setSession] = useState(0);
  const [deleting, setDeleting] = useState<CustomStrategySummary | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const open = (id: string | null) => {
    setSession((n) => n + 1);
    setEditing({ id });
  };

  const upsert = (s: CustomStrategySummary) =>
    custom.setData((list = []) => (list.some((x) => x.id === s.id) ? list.map((x) => (x.id === s.id ? s : x)) : [s, ...list]));

  const run = async (id: string, action: () => Promise<void>) => {
    setBusyId(id);
    try {
      await action();
    } catch (e) {
      notify(errorText(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const toggleVisibility = (s: CustomStrategySummary) =>
    run(s.id, async () => {
      const updated = await services.strategies.updateCustom(s.id, { visibility: s.visibility === 'public' ? 'private' : 'public' });
      upsert(toSummary(updated));
      notify(updated.visibility === 'public' ? `“${updated.name}” is now public.` : `“${updated.name}” is now private.`, 'success');
    });

  const clone = (s: CustomStrategySummary) =>
    run(s.id, async () => {
      const copy = await services.strategies.cloneCustom(s.id);
      upsert(toSummary(copy));
      notify(`Created “${copy.name}”.`, 'success');
    });

  const remove = () => {
    const target = deleting;
    if (!target) return;
    void run(target.id, async () => {
      await services.strategies.removeCustom(target.id);
      custom.setData((list) => (list ?? []).filter((x) => x.id !== target.id));
      notify(`“${target.name}” deleted.`, 'info');
      setDeleting(null);
    });
  };

  return (
    <Panel
      title="Custom strategies"
      meta={custom.data && <span>{custom.data.length} total</span>}
      actions={
        <Button size="sm" variant="primary" icon={Plus} onClick={() => open(null)}>
          New strategy
        </Button>
      }
      flush
    >
      {custom.status === 'loading' ? (
        <Loading label="Loading custom strategies">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : custom.status === 'error' && !custom.data ? (
        <ErrorState error={custom.error} onRetry={custom.reload} compact />
      ) : !custom.data?.length ? (
        <EmptyState
          title="No custom strategies"
          description="Combine indicator rules (builder) or let several strategies vote (composite). They work everywhere a platform strategy does."
          action={
            <Button size="sm" icon={Plus} onClick={() => open(null)}>
              New strategy
            </Button>
          }
        />
      ) : (
        <ul className="divide-y divide-line">
          {custom.data.map((s) => (
            <li key={s.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                  {s.name}
                  <Badge>{s.kind === 'builder' ? 'Builder' : 'Composite'}</Badge>
                  <Badge tone={s.visibility === 'public' ? 'info' : 'neutral'}>{s.visibility === 'public' ? 'Public' : 'Private'}</Badge>
                </p>
                <p className="text-xs text-fg-3">
                  <span className="num">v{s.version}</span> · updated {formatDate(s.updatedAt, timeZone)}
                  {s.clonedFrom ? ' · cloned' : ''}
                  {s.description ? ` · ${s.description}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <IconButton icon={Pencil} label={`Edit ${s.name}`} size="sm" disabled={busyId === s.id} onClick={() => open(s.id)} />
                <IconButton icon={LineChart} label={`Preview ${s.name}`} size="sm" onClick={() => onPreview(s)} />
                <IconButton
                  icon={s.visibility === 'public' ? Lock : Globe}
                  label={s.visibility === 'public' ? `Make ${s.name} private` : `Publish ${s.name}`}
                  size="sm"
                  disabled={busyId === s.id}
                  onClick={() => void toggleVisibility(s)}
                />
                <IconButton icon={Copy} label={`Clone ${s.name}`} size="sm" disabled={busyId === s.id} onClick={() => void clone(s)} />
                <IconButton icon={Trash2} label={`Delete ${s.name}`} size="sm" disabled={busyId === s.id} onClick={() => setDeleting(s)} tooltipSide="left" />
              </div>
            </li>
          ))}
        </ul>
      )}

      <CustomStrategyDialog
        key={session}
        target={editing}
        onClose={() => setEditing(null)}
        onSaved={(s) => {
          upsert(toSummary(s));
          setEditing(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this strategy?"
        description={`“${deleting?.name ?? ''}” will be deleted. The server refuses if one of your composites still uses it.`}
        confirmLabel="Delete strategy"
        busy={busyId !== null && busyId === deleting?.id}
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
