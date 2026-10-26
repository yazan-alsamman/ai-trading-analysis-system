import { ArrowDown, ArrowUp, CloudDownload, CloudUpload, Copy, Pencil, Plus, Share2, Star, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useAuth, usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Input } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { ServerWorkspace, ServerWorkspaceSummary, WorkspaceStateDoc } from '@/domain/serverWorkspaces';
import { useResource } from '@/hooks/useResource';
import { formatRelative } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';
import { fromServerState, toServerState } from './workspaceState';
import { WorkspaceShareDialog } from './WorkspaceShareDialog';

/** Roles the server lets share a workspace (docs/workspaces.md; 403 for traders). */
const SHARING_ROLES = ['analyst', 'expert', 'admin'];

/** A push refused with 409: the server copy changed since it was listed. */
interface Conflict {
  workspace: ServerWorkspaceSummary;
  state: WorkspaceStateDoc;
  serverVersion: number | null;
}

/** Events within this window after our own change are ours echoed back by the WebSocket. */
const OWN_ECHO_MS = 5000;

function RenameDialog({ target, onClose, onSave }: { target: ServerWorkspaceSummary | null; onClose: () => void; onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastId, setLastId] = useState<string | null>(null);
  if ((target?.id ?? null) !== lastId) {
    setLastId(target?.id ?? null);
    setName(target?.name ?? '');
    setError(null);
  }
  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 60) return setError('Use 1–60 characters.');
    setBusy(true);
    try {
      await onSave(trimmed);
    } catch (e) {
      setError(isApiError(e) && e.kind === 'conflict' ? 'You already have a workspace with this name (names ignore case).' : userMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      title="Rename server workspace"
      size="sm"
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="server-ws-name" loading={busy}>
            Save
          </Button>
        </>
      }
    >
      <form
        id="server-ws-name"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Field label="Workspace name">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} autoFocus maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <div className="mt-3">
          <FormError message={error} />
        </div>
      </form>
    </Dialog>
  );
}

/**
 * Backend mode: workspaces saved on the server (docs/workspaces.md), shared
 * with the mobile app. Every push carries the version it edited; when another
 * device saved first the server answers 409 and the user chooses what wins.
 */
export function ServerWorkspacesSection() {
  const services = useServices();
  const { activeWorkspace, createWorkspace, updateWorkspace } = usePreferences();
  const { notify } = useToast();
  const list = useResource('server-workspaces', (signal) => services.workspacesSync.list({ signal }));
  const instruments = useResource('instrument-directory', (signal) => services.instruments.list({ signal }));
  const [busy, setBusy] = useState<string | null>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [renaming, setRenaming] = useState<ServerWorkspaceSummary | null>(null);
  const [deleting, setDeleting] = useState<ServerWorkspaceSummary | null>(null);
  const [sharing, setSharing] = useState<ServerWorkspaceSummary | null>(null);
  const canShare = SHARING_ROLES.includes(useAuth().session?.user.role ?? '');
  const [error, setError] = useState<string | null>(null);
  const lastOwnChange = useRef(0);

  // Changes from other devices arrive on the user's WebSocket topic.
  const reload = list.reload;
  useEffect(
    () =>
      services.workspacesSync.subscribe(() => {
        reload();
        if (Date.now() - lastOwnChange.current > OWN_ECHO_MS) notify('A server workspace was changed on another device. The list is up to date.', 'info');
      }),
    [services, reload, notify],
  );

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    lastOwnChange.current = Date.now();
    try {
      await action();
    } catch (e) {
      setError(userMessage(e));
    } finally {
      lastOwnChange.current = Date.now();
      setBusy(null);
    }
  };

  const mapped = () => {
    const { state, skipped } = toServerState(activeWorkspace, instruments.data ?? []);
    if (skipped.length) notify(`Not saved on the server: ${skipped.join(', ')}.`, 'warning');
    return state;
  };

  const loadIntoBrowser = (ws: ServerWorkspace) => {
    const { patch, skipped } = fromServerState(ws.state, instruments.data ?? [], activeWorkspace.indicators.includes('volume'));
    const local = createWorkspace(ws.name.slice(0, 40));
    updateWorkspace(patch, local.id);
    notify(
      skipped.length ? `Loaded “${ws.name}” as a new browser workspace. Not shown here: ${skipped.join(', ')}.` : `Loaded “${ws.name}” as a new browser workspace and made it active.`,
      skipped.length ? 'warning' : 'success',
    );
  };

  const saveNew = () =>
    run('create', async () => {
      try {
        const created = await services.workspacesSync.create({ name: activeWorkspace.name, state: mapped() });
        list.setData((l) => [...(l ?? []), created]);
        notify(`“${created.name}” saved on the server.`, 'success');
      } catch (e) {
        if (!isApiError(e) || e.kind !== 'conflict') throw e;
        setError(`A server workspace named “${activeWorkspace.name}” already exists. Push into it, or rename one of them.`);
      }
    });

  /** Replaces the server state if it is still at `version`; a 409 opens the conflict dialog. */
  const replaceState = async (ws: ServerWorkspaceSummary, state: WorkspaceStateDoc, version: number) => {
    try {
      const saved = await services.workspacesSync.replaceState(ws.id, state, version);
      list.setData((l) => (l ?? []).map((x) => (x.id === saved.id ? saved : x)));
      setConflict(null);
      notify(`“${saved.name}” updated on the server (version ${saved.version}).`, 'success');
    } catch (e) {
      if (!isApiError(e) || e.kind !== 'conflict') throw e;
      const current = e.data?.current_version;
      setConflict({ workspace: ws, state, serverVersion: typeof current === 'number' ? current : null });
    }
  };

  const push = (ws: ServerWorkspaceSummary, state: WorkspaceStateDoc, version: number) => run(`push:${ws.id}`, () => replaceState(ws, state, version));

  const resolveWithServer = (c: Conflict) =>
    run(`resolve:${c.workspace.id}`, async () => {
      const latest = await services.workspacesSync.get(c.workspace.id);
      list.setData((l) => (l ?? []).map((x) => (x.id === latest.id ? latest : x)));
      setConflict(null);
      loadIntoBrowser(latest);
    });

  const overwrite = (c: Conflict) =>
    run(`resolve:${c.workspace.id}`, async () => {
      // Explicit user choice: re-read the latest version, then replace it with the browser layout.
      const latest = await services.workspacesSync.get(c.workspace.id);
      await replaceState(latest, c.state, latest.version);
    });

  const mutate = (key: string, action: () => Promise<void>) => void run(key, action);

  /** Tab order: the server needs every id, in the new order. */
  const move = (index: number, delta: -1 | 1) => {
    const ids = (list.data ?? []).map((w) => w.id);
    const to = index + delta;
    const moved = ids[index];
    if (moved === undefined || to < 0 || to >= ids.length) return;
    ids.splice(index, 1);
    ids.splice(to, 0, moved);
    mutate(`move:${moved}`, async () => {
      const ordered = await services.workspacesSync.reorder(ids);
      list.setData(() => ordered);
    });
  };
  const rows = list.data ?? [];
  const disabled = busy !== null;

  return (
    <div id="server-workspaces" className="scroll-mt-4">
      <Panel
        title="Server workspaces"
        meta={<span>Saved on your account and shared with the mobile app</span>}
        actions={
          <Button size="sm" icon={Plus} loading={busy === 'create'} disabled={disabled || !instruments.data} onClick={() => void saveNew()}>
            Save current layout
          </Button>
        }
        flush
      >
        {list.status === 'loading' ? (
          <Loading label="Loading server workspaces">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : list.status === 'error' && !list.data ? (
          <ErrorState error={list.error} onRetry={list.reload} compact />
        ) : rows.length === 0 ? (
          <EmptyState compact title="No server workspaces" description="Save your current layout to continue on another device." />
        ) : (
          <ul className="divide-y divide-line">
            {rows.map((w, index) => (
              <li key={w.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
                {rows.length > 1 && (
                  <div className="flex flex-col">
                    <IconButton icon={ArrowUp} label={`Move ${w.name} up`} size="sm" disabled={disabled || index === 0} onClick={() => move(index, -1)} tooltipSide="right" />
                    <IconButton icon={ArrowDown} label={`Move ${w.name} down`} size="sm" disabled={disabled || index === rows.length - 1} onClick={() => move(index, 1)} tooltipSide="right" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                    {w.name}
                    {w.isDefault && <Badge tone="accent">Default</Badge>}
                    {w.isShared && <Badge tone="info">Shared</Badge>}
                  </p>
                  <p className="text-xs text-fg-3">
                    Version {w.version} · {w.panelCount} chart{w.panelCount === 1 ? '' : 's'} · updated {formatRelative(w.updatedAt)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={CloudDownload}
                  disabled={disabled || !instruments.data}
                  loading={busy === `load:${w.id}`}
                  onClick={() =>
                    mutate(`load:${w.id}`, async () => {
                      loadIntoBrowser(await services.workspacesSync.get(w.id));
                    })
                  }
                >
                  Load
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={CloudUpload}
                  disabled={disabled || !instruments.data}
                  loading={busy === `push:${w.id}`}
                  onClick={() => void push(w, mapped(), w.version)}
                  title={`Replace “${w.name}” with the active browser workspace “${activeWorkspace.name}”`}
                >
                  Push current
                </Button>
                {!w.isDefault && (
                  <IconButton
                    icon={Star}
                    label={`Make ${w.name} the default`}
                    size="sm"
                    disabled={disabled}
                    onClick={() =>
                      mutate(`default:${w.id}`, async () => {
                        await services.workspacesSync.update(w.id, { isDefault: true });
                        list.reload();
                      })
                    }
                    tooltipSide="left"
                  />
                )}
                {canShare && <IconButton icon={Share2} label={w.isShared ? `Share link of ${w.name}` : `Share ${w.name}`} size="sm" disabled={disabled} onClick={() => setSharing(w)} tooltipSide="left" />}
                <IconButton icon={Pencil} label={`Rename ${w.name}`} size="sm" disabled={disabled} onClick={() => setRenaming(w)} tooltipSide="left" />
                <IconButton
                  icon={Copy}
                  label={`Duplicate ${w.name}`}
                  size="sm"
                  disabled={disabled}
                  onClick={() =>
                    mutate(`dup:${w.id}`, async () => {
                      const copy = await services.workspacesSync.duplicate(w.id);
                      list.setData((l) => [...(l ?? []), copy]);
                      notify(`Duplicated as “${copy.name}”.`, 'success');
                    })
                  }
                  tooltipSide="left"
                />
                <IconButton icon={Trash2} label={`Delete ${w.name}`} size="sm" disabled={disabled} onClick={() => setDeleting(w)} tooltipSide="left" />
              </li>
            ))}
          </ul>
        )}
        {error && (
          <div className="border-t border-line px-4 py-2.5">
            <FormError message={error} />
          </div>
        )}
        <p className="border-t border-line px-4 py-2.5 text-xs text-fg-3">
          “Push current” replaces the server copy with the active browser workspace (“{activeWorkspace.name}”). If it was changed on another device since it was listed, you
          choose which version to keep. This website edits one chart per workspace; extra panels, drawings and strategy overlays made in the mobile app are kept on the server
          only when you do not push over them.
          {canShare ? ' You can share a workspace read-only by link.' : ' Analysts, experts and admins can share workspaces by link.'}
        </p>
      </Panel>

      <Dialog
        open={conflict !== null}
        onClose={() => setConflict(null)}
        title="Changed on another device"
        description={
          conflict
            ? `“${conflict.workspace.name}” was saved elsewhere after this list was loaded${conflict.serverVersion !== null ? ` (the server is now at version ${conflict.serverVersion}, you edited version ${conflict.workspace.version})` : ''}. Nothing was overwritten.`
            : undefined
        }
        footer={
          conflict && (
            <>
              <Button onClick={() => setConflict(null)} disabled={disabled}>
                Cancel
              </Button>
              <Button icon={CloudDownload} onClick={() => void resolveWithServer(conflict)} loading={busy === `resolve:${conflict.workspace.id}`} disabled={disabled}>
                Load server version
              </Button>
              <Button variant="danger" icon={CloudUpload} onClick={() => void overwrite(conflict)} disabled={disabled}>
                Overwrite with mine
              </Button>
            </>
          )
        }
      >
        <p className="text-sm text-fg-2">
          <strong className="font-medium text-fg">Load server version</strong> opens the newer server copy as a new browser workspace.{' '}
          <strong className="font-medium text-fg">Overwrite with mine</strong> replaces the server copy with your active browser workspace; the other device’s change is lost.
        </p>
      </Dialog>

      {sharing && (
        <WorkspaceShareDialog
          key={sharing.id}
          target={sharing}
          onClose={() => setSharing(null)}
          onChanged={(isShared) => {
            lastOwnChange.current = Date.now();
            list.setData((l) => (l ?? []).map((x) => (x.id === sharing.id ? { ...x, isShared } : x)));
            setSharing((cur) => (cur ? { ...cur, isShared } : cur));
          }}
        />
      )}

      <RenameDialog
        target={renaming}
        onClose={() => setRenaming(null)}
        onSave={async (name) => {
          lastOwnChange.current = Date.now();
          const saved = await services.workspacesSync.update(renaming?.id ?? '', { name });
          list.setData((l) => (l ?? []).map((x) => (x.id === saved.id ? saved : x)));
          setRenaming(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete server workspace?"
        description={`“${deleting?.name ?? ''}” will be removed from your account on every device. Browser workspaces are not affected.`}
        confirmLabel="Delete workspace"
        busy={busy !== null && busy === `delete:${deleting?.id ?? ''}`}
        onConfirm={() =>
          mutate(`delete:${deleting?.id ?? ''}`, async () => {
            if (!deleting) return;
            await services.workspacesSync.remove(deleting.id);
            setDeleting(null);
            list.reload();
          })
        }
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
