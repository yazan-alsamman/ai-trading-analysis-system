import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { useState } from 'react';
import { useAuth, usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Field, Input, Select } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminUser } from '@/domain/admin';
import { ROLE_LABELS, type UserRole } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { userMessage } from '@/services/errors';

const PAGE = 20;
const ROLES = Object.keys(ROLE_LABELS) as UserRole[];

type Pending = { kind: 'role'; user: AdminUser; role: UserRole } | { kind: 'active'; user: AdminUser; active: boolean };

/** Admin › Users: search, role and status changes (PATCH /admin/users/{id}/role|status). */
export function AdminUsersPage() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const myId = useAuth().session?.user.id;
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [role, setRole] = useState<UserRole | ''>('');
  const [active, setActive] = useState<'' | 'true' | 'false'>('');
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);

  const key = `admin:users:${query}:${role}:${active}:${offset}`;
  const res = useResource(key, (signal) =>
    services.admin.users(
      { limit: PAGE, offset, ...(role ? { role } : {}), ...(active ? { isActive: active === 'true' } : {}), ...(query ? { search: query } : {}) },
      { signal },
    ),
  );

  const replace = (u: AdminUser) => res.setData((prev) => ({ total: prev?.total ?? 0, items: (prev?.items ?? []).map((x) => (x.id === u.id ? u : x)) }));

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const u = pending.kind === 'role' ? await services.admin.setRole(pending.user.id, pending.role) : await services.admin.setActive(pending.user.id, pending.active);
      replace(u);
      notify(pending.kind === 'role' ? `${u.email} is now ${ROLE_LABELS[u.role]}.` : `${u.email} was ${u.isActive ? 'activated' : 'deactivated'}.`, 'success');
      setPending(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  const description = (() => {
    if (!pending) return '';
    const who = pending.user.email;
    if (pending.kind === 'active')
      return pending.active ? `${who} will be able to sign in again.` : `${who} will be signed out and cannot sign in until reactivated. Their data is kept.`;
    const demotesAdmin = pending.user.role === 'admin' && pending.role !== 'admin';
    return `${who}: ${ROLE_LABELS[pending.user.role]} → ${ROLE_LABELS[pending.role]}. ${
      demotesAdmin ? 'This removes their administrator access, including this console.' : pending.role === 'admin' ? 'Admins can manage every user and all platform data.' : 'Their permissions change at their next request.'
    }`;
  })();

  return (
    <Panel title="Users" meta={res.data && <span>{res.data.total} total</span>} flush>
      <form
        className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setQuery(search.trim());
        }}
      >
        <Field label="Search" className="w-full sm:w-64">
          {({ id }) => <Input id={id} type="search" placeholder="Email or name" value={search} maxLength={320} onChange={(e) => setSearch(e.target.value)} />}
        </Field>
        <Field label="Role" className="w-full sm:w-36">
          {({ id }) => (
            <Select
              id={id}
              value={role}
              onChange={(e) => {
                setOffset(0);
                setRole(e.target.value as UserRole | '');
              }}
            >
              <option value="">All roles</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Status" className="w-full sm:w-36">
          {({ id }) => (
            <Select
              id={id}
              value={active}
              onChange={(e) => {
                setOffset(0);
                setActive(e.target.value as '' | 'true' | 'false');
              }}
            >
              <option value="">Any</option>
              <option value="true">Active</option>
              <option value="false">Deactivated</option>
            </Select>
          )}
        </Field>
        <Button type="submit" icon={Search}>
          Search
        </Button>
      </form>

      {res.status === 'loading' ? (
        <Loading label="Loading users">
          <SkeletonRows rows={6} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title="No users match" description="Change the search or filters." />
      ) : (
        <>
          <TableRegion label="Users">
            <thead>
              <tr>
                <Th>Email</Th>
                <Th>Name</Th>
                <Th>Role</Th>
                <Th>Status</Th>
                <Th>Joined</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((u) => {
                const isMe = u.id === myId;
                return (
                  <tr key={u.id}>
                    <Td>
                      {u.email}
                      {isMe && <Badge className="ml-1.5">You</Badge>}
                    </Td>
                    <Td>{u.name ?? '—'}</Td>
                    <Td>
                      <Select
                        aria-label={`Role of ${u.email}`}
                        className="h-8 w-32"
                        value={u.role}
                        disabled={isMe}
                        title={isMe ? 'You cannot change your own role.' : undefined}
                        onChange={(e) => setPending({ kind: 'role', user: u, role: e.target.value as UserRole })}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </Select>
                    </Td>
                    <Td>{u.isActive ? <Badge tone="up">Active</Badge> : <Badge tone="danger">Deactivated</Badge>}</Td>
                    <Td className="text-fg-2">{formatDate(u.createdAt, timeZone)}</Td>
                    <Td>
                      <Button
                        size="sm"
                        variant={u.isActive ? 'ghost' : 'secondary'}
                        disabled={isMe}
                        title={isMe ? 'You cannot deactivate your own account.' : undefined}
                        onClick={() => setPending({ kind: 'active', user: u, active: !u.isActive })}
                      >
                        {u.isActive ? 'Deactivate' : 'Activate'}
                      </Button>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </TableRegion>
          {res.data.total > PAGE && (
            <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2 text-xs text-fg-3">
              <span>
                {offset + 1}–{Math.min(offset + PAGE, res.data.total)} of {res.data.total}
              </span>
              <div className="flex gap-2">
                <Button size="sm" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
                  Previous
                </Button>
                <Button size="sm" trailingIcon={ChevronRight} disabled={offset + PAGE >= res.data.total} onClick={() => setOffset((o) => o + PAGE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={pending !== null}
        title={pending?.kind === 'role' ? 'Change role?' : pending?.kind === 'active' && pending.active ? 'Activate account?' : 'Deactivate account?'}
        description={description}
        confirmLabel={pending?.kind === 'role' ? 'Change role' : pending?.kind === 'active' && pending.active ? 'Activate' : 'Deactivate'}
        destructive={pending?.kind === 'active' ? !pending.active : pending?.user.role === 'admin'}
        busy={busy}
        onConfirm={() => void confirm()}
        onCancel={() => setPending(null)}
      />
    </Panel>
  );
}
