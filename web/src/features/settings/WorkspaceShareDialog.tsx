import { Copy, Link2, Link2Off } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Button, IconButton } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { FormError, Input } from '@/components/ui/Form';
import { Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { ServerWorkspaceSummary } from '@/domain/serverWorkspaces';
import { useResource } from '@/hooks/useResource';
import { userMessage } from '@/services/errors';

const linkFor = (slug: string) => `${window.location.origin}/workspaces/shared/${encodeURIComponent(slug)}`;

/**
 * A read-only link to one server workspace (docs/workspaces.md: analysts,
 * experts and admins). Anyone signed in can open it and copy the workspace;
 * stopping the share makes the old link answer 404.
 */
export function WorkspaceShareDialog({ target, onClose, onChanged }: { target: ServerWorkspaceSummary; onClose: () => void; onChanged: (isShared: boolean) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  // An already shared workspace: its slug comes with the full workspace.
  const current = useResource(`ws-share:${target.id}:${target.isShared ? 'shared' : 'private'}`, (signal) =>
    target.isShared ? services.workspacesSync.get(target.id, { signal }).then((w) => w.shareSlug) : Promise.resolve(null),
  );
  const activeSlug = slug ?? current.data ?? null;

  const act = async (share: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const r = share ? await services.workspacesSync.share(target.id) : await services.workspacesSync.unshare(target.id);
      setSlug(r.isShared ? r.slug : null);
      onChanged(r.isShared);
      notify(r.isShared ? 'Share link created.' : 'Sharing stopped. The old link no longer works.', r.isShared ? 'success' : 'info');
      if (!r.isShared) onClose();
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const copy = (link: string) =>
    navigator.clipboard
      .writeText(link)
      .then(() => notify('Link copied.', 'success'))
      .catch(() => notify('Could not copy. Select the link and copy it manually.', 'warning'));

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Share “${target.name}”`}
      description="Anyone signed in to the platform can open the link, see this workspace read-only and copy it into their own. Your later changes do not change their copies."
      size="sm"
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Close
          </Button>
          {activeSlug ? (
            <Button variant="danger" icon={Link2Off} onClick={() => void act(false)} loading={busy}>
              Stop sharing
            </Button>
          ) : (
            <Button variant="primary" icon={Link2} onClick={() => void act(true)} loading={busy} disabled={current.status === 'loading'}>
              Create share link
            </Button>
          )}
        </>
      }
    >
      {current.status === 'loading' ? (
        <Loading label="Loading the share link">
          <SkeletonRows rows={1} />
        </Loading>
      ) : activeSlug ? (
        <div className="flex items-center gap-2">
          <Input readOnly value={linkFor(activeSlug)} aria-label="Share link" onFocus={(e) => e.target.select()} />
          <IconButton icon={Copy} label="Copy share link" onClick={() => void copy(linkFor(activeSlug))} tooltipSide="left" />
        </div>
      ) : (
        <p className="text-sm text-fg-2">This workspace is private.</p>
      )}
      <div className="mt-3">
        <FormError message={error ?? (current.status === 'error' ? userMessage(current.error) : null)} />
      </div>
    </Dialog>
  );
}
