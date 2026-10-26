import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminApiKey } from '@/domain/admin';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatRelative, MISSING } from '@/lib/format';
import { userMessage } from '@/services/errors';

const PAGE = 20;

/** Admin › API access: every user's API keys (docs/api-keys.md); revoking takes effect on the key's next request. */
export function AdminAccessPage() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [filter, setFilter] = useState<'active' | 'revoked' | 'all'>('active');
  const [offset, setOffset] = useState(0);
  const [revoking, setRevoking] = useState<AdminApiKey | null>(null);
  const [busy, setBusy] = useState(false);
  const res = useResource(`admin:keys:${filter}:${offset}`, (signal) =>
    services.admin.apiKeys({ limit: PAGE, offset, ...(filter !== 'all' ? { revoked: filter === 'revoked' } : {}) }, { signal }),
  );

  const revoke = async () => {
    if (!revoking) return;
    setBusy(true);
    try {
      await services.admin.revokeApiKey(revoking.id);
      notify(`Key “${revoking.name}” of ${revoking.ownerEmail} was revoked.`, 'success');
      setRevoking(null);
      res.reload();
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="API keys"
      meta={<span>Read-only programmatic access. The secret is shown to its owner once and never stored in clear.</span>}
      actions={
        <SegmentedControl
          label="Key status"
          value={filter}
          onChange={(v) => {
            setOffset(0);
            setFilter(v);
          }}
          options={[
            { value: 'active', label: 'Active' },
            { value: 'revoked', label: 'Revoked' },
            { value: 'all', label: 'All' },
          ]}
        />
      }
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading API keys">
          <SkeletonRows rows={4} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title="No API keys" />
      ) : (
        <>
          <TableRegion label="All API keys">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Owner</Th>
                <Th>Prefix</Th>
                <Th>Scopes</Th>
                <Th numeric>Limit/min</Th>
                <Th>Last used</Th>
                <Th>Expires</Th>
                <Th>Status</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((k) => (
                <tr key={k.id}>
                  <Td>{k.name}</Td>
                  <Td>{k.ownerEmail}</Td>
                  <Td className="font-mono text-xs">{k.prefix}…</Td>
                  <Td className="whitespace-normal">
                    <div className="flex flex-wrap gap-1">
                      {k.scopes.map((s) => (
                        <Badge key={s}>{s}</Badge>
                      ))}
                    </div>
                  </Td>
                  <Td numeric>{k.rateLimitPerMinute ?? 'Default'}</Td>
                  <Td className="text-fg-2">{k.lastUsedAt ? formatRelative(k.lastUsedAt) : 'Never'}</Td>
                  <Td className="text-fg-2">{k.expiresAt ? formatDate(k.expiresAt, timeZone) : MISSING}</Td>
                  <Td>{k.revoked ? <Badge tone="danger">Revoked</Badge> : <Badge tone="up">Active</Badge>}</Td>
                  <Td>
                    {!k.revoked && (
                      <Button size="sm" variant="ghost" onClick={() => setRevoking(k)}>
                        Revoke
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
          {res.data.total > PAGE && (
            <div className="flex justify-end gap-2 border-t border-line px-4 py-2">
              <Button size="sm" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
                Previous
              </Button>
              <Button size="sm" trailingIcon={ChevronRight} disabled={offset + PAGE >= res.data.total} onClick={() => setOffset((o) => o + PAGE)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
      <ConfirmDialog
        open={revoking !== null}
        title="Revoke API key?"
        description={`“${revoking?.name ?? ''}” (${revoking?.prefix ?? ''}…) of ${revoking?.ownerEmail ?? ''} stops working immediately. This cannot be undone; the owner must create a new key.`}
        confirmLabel="Revoke key"
        busy={busy}
        onConfirm={() => void revoke()}
        onCancel={() => setRevoking(null)}
      />
    </Panel>
  );
}
