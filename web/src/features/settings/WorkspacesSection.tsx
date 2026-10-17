import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Field, Input } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { getInstrument } from '@/domain/instruments';
import type { Workspace } from '@/domain/preferences';
import { workspaceNameSchema } from './schemas';

function NameDialog({ open, title, initial, onSave, onClose }: { open: boolean; title: string; initial: string; onSave: (name: string) => void; onClose: () => void }) {
  const [name, setName] = useState(initial);
  const [error, setError] = useState<string | undefined>();
  const [lastInitial, setLastInitial] = useState(initial);
  if (initial !== lastInitial) {
    setLastInitial(initial);
    setName(initial);
    setError(undefined);
  }
  const submit = () => {
    const parsed = workspaceNameSchema.safeParse(name);
    if (!parsed.success) return setError(parsed.error.issues[0]?.message);
    onSave(parsed.data);
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="workspace-name-form">
            Save
          </Button>
        </>
      }
    >
      <form
        id="workspace-name-form"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <Field label="Workspace name" error={error}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} aria-describedby={describedBy} invalid={invalid} value={name} autoFocus maxLength={60} onChange={(e) => setName(e.target.value)} />
          )}
        </Field>
      </form>
    </Dialog>
  );
}

/** SF18 — multiple workspaces per user. */
export function WorkspacesSection({ persistenceNote }: { persistenceNote: string }) {
  const { prefs, createWorkspace, updateWorkspace, deleteWorkspace, setActiveWorkspace } = usePreferences();
  const { notify } = useToast();
  const [renaming, setRenaming] = useState<Workspace | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Workspace | null>(null);
  const onlyOne = prefs.workspaces.length <= 1;

  return (
    <Panel
      title="Workspaces"
      meta={<span>Each workspace remembers its instrument, timeframe, chart type, indicators and AI layers</span>}
      actions={
        <Button size="sm" icon={Plus} onClick={() => setCreating(true)}>
          New workspace
        </Button>
      }
      flush
    >
      <ul className="divide-y divide-line">
        {prefs.workspaces.map((w) => {
          const active = w.id === prefs.activeWorkspaceId;
          return (
            <li key={w.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium text-fg">
                  {w.name} {active && <Badge tone="accent">Active</Badge>}
                </p>
                <p className="text-xs text-fg-3">
                  {getInstrument(w.symbol).display} · {w.timeframe} · {w.chartType} · {w.indicators.length} indicators
                </p>
              </div>
              {!active && (
                <Button size="sm" variant="ghost" icon={Check} onClick={() => setActiveWorkspace(w.id)}>
                  Make active
                </Button>
              )}
              <IconButton icon={Pencil} label={`Rename ${w.name}`} size="sm" onClick={() => setRenaming(w)} tooltipSide="left" />
              <IconButton
                icon={Trash2}
                label={onlyOne ? 'At least one workspace is required' : `Delete ${w.name}`}
                size="sm"
                disabled={onlyOne}
                onClick={() => setDeleting(w)}
                tooltipSide="left"
              />
            </li>
          );
        })}
      </ul>
      <p className="border-t border-line px-4 py-2.5 text-xs text-fg-3">{persistenceNote}</p>

      <NameDialog
        open={creating}
        title="New workspace"
        initial={`Workspace ${prefs.workspaces.length + 1}`}
        onClose={() => setCreating(false)}
        onSave={(name) => {
          createWorkspace(name);
          setCreating(false);
          notify(`Workspace “${name}” created and activated.`, 'success');
        }}
      />
      <NameDialog
        open={renaming !== null}
        title="Rename workspace"
        initial={renaming?.name ?? ''}
        onClose={() => setRenaming(null)}
        onSave={(name) => {
          if (renaming) updateWorkspace({ name }, renaming.id);
          setRenaming(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete workspace?"
        description={`“${deleting?.name ?? ''}” and its layout will be removed. Alerts and other data are not affected.`}
        confirmLabel="Delete workspace"
        onConfirm={() => {
          if (deleting) deleteWorkspace(deleting.id);
          setDeleting(null);
        }}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
