import { ChevronLeft, ChevronRight, EyeOff, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Textarea } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminReport } from '@/domain/admin';
import { ROLE_LABELS } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatRelative, MISSING } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { rec, text } from './overviewData';

const PAGE = 20;
const NOTE_MAX = 300;
const TARGET_LABEL = { post: 'Post', comment: 'Comment', message: 'Chat message' } as const;

function ResolveDialog({ report, onClose, onResolved }: { report: AdminReport; onClose: () => void; onResolved: () => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<'hide' | 'dismiss' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resolve = async (action: 'hide' | 'dismiss') => {
    setBusy(action);
    setError(null);
    try {
      await services.admin.resolveReport(report.id, action, action === 'hide' ? note.trim() : '');
      notify(action === 'hide' ? 'Content hidden. Every open report on it was resolved and the author was notified.' : 'Report dismissed. Every open report on this content was resolved.', 'success');
      onResolved();
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(null);
    }
  };
  const target = report.target;
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Resolve report on a ${TARGET_LABEL[report.targetType].toLowerCase()}`}
      description="Hide: the content disappears for everyone but its author, who is notified (with your note). Dismiss: nothing changes. Either way every open report on the same content is resolved."
      footer={
        <>
          <Button onClick={onClose} disabled={busy !== null}>
            Cancel
          </Button>
          <Button icon={X} onClick={() => void resolve('dismiss')} loading={busy === 'dismiss'} disabled={busy === 'hide'}>
            Dismiss
          </Button>
          <Button variant="danger" icon={EyeOff} onClick={() => void resolve('hide')} loading={busy === 'hide'} disabled={busy === 'dismiss'}>
            Hide content
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-md border border-line bg-inset p-3 text-sm">
          <p className="text-xs text-fg-3">Reason given by {report.reporter?.name ?? 'a deleted user'}</p>
          <p className="mt-1 text-fg">{report.reason}</p>
        </div>
        {target && (
          <div className="rounded-md border border-line p-3 text-sm">
            <p className="text-xs text-fg-3">
              {text(rec(target.author)?.display_name)} · {text(target.status)}
            </p>
            {typeof target.title === 'string' && <p className="mt-1 font-medium text-fg">{target.title}</p>}
            <p className="mt-1 whitespace-pre-line text-fg-2">{text(target.excerpt)}</p>
          </div>
        )}
        <Field label="Note to the author" optional hint={`Sent with the hide notification (${note.length}/${NOTE_MAX}).`}>
          {({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} rows={3} maxLength={NOTE_MAX} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>
        <FormError message={error} />
      </div>
    </Dialog>
  );
}

function Reports() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const [status, setStatus] = useState<'open' | 'resolved' | 'all'>('open');
  const [offset, setOffset] = useState(0);
  const [resolving, setResolving] = useState<AdminReport | null>(null);
  const res = useResource(`admin:reports:${status}:${offset}`, (signal) => services.admin.reports({ status, limit: PAGE, offset }, { signal }));

  return (
    <Panel
      title="Reports"
      meta={res.data && <span>{res.data.total} {status === 'all' ? 'total' : status}</span>}
      actions={
        <SegmentedControl
          label="Report status"
          value={status}
          onChange={(v) => {
            setOffset(0);
            setStatus(v);
          }}
          options={[
            { value: 'open', label: 'Open' },
            { value: 'resolved', label: 'Resolved' },
            { value: 'all', label: 'All' },
          ]}
        />
      }
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading reports">
          <SkeletonRows rows={4} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title={status === 'open' ? 'No open reports' : 'No reports'} description="Reports users file on posts, comments and chat messages appear here." />
      ) : (
        <>
          <ul className="divide-y divide-line" aria-label="Reports">
            {res.data.items.map((r) => {
              const t = r.target;
              const postId = typeof t?.post_id === 'string' ? t.post_id : null;
              return (
                <li key={r.id} className="flex flex-col gap-2 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge>{TARGET_LABEL[r.targetType]}</Badge>
                    {r.status === 'open' ? <Badge tone="warning">Open</Badge> : <Badge tone="neutral">Resolved{r.resolution ? `: ${r.resolution}` : ''}</Badge>}
                    {r.openReportsOnTarget > 1 && <Badge tone="danger">{r.openReportsOnTarget} open reports on this content</Badge>}
                    <span className="text-xs text-fg-3" title={formatDateTime(r.createdAt, timeZone)}>
                      {formatRelative(r.createdAt)} by {r.reporter ? `${r.reporter.name} (${ROLE_LABELS[r.reporter.role]})` : 'a deleted user'}
                    </span>
                  </div>
                  <p className="text-sm text-fg">
                    <span className="text-fg-3">Reason: </span>
                    {r.reason}
                  </p>
                  {t && (
                    <blockquote className="rounded-md border-l-2 border-line-strong bg-inset px-3 py-2 text-sm">
                      <p className="text-xs text-fg-3">
                        {text(rec(t.author)?.display_name)} · content {text(t.status)}
                      </p>
                      {typeof t.title === 'string' && <p className="font-medium text-fg">{t.title}</p>}
                      <p className="line-clamp-3 whitespace-pre-line text-fg-2">{text(t.excerpt)}</p>
                      {postId && (
                        <Link to="/community/posts" className="mt-1 inline-block text-xs text-accent underline-offset-2 hover:underline">
                          Open the posts feed
                        </Link>
                      )}
                    </blockquote>
                  )}
                  {r.status === 'open' && (
                    <div>
                      <Button size="sm" onClick={() => setResolving(r)}>
                        Resolve…
                      </Button>
                    </div>
                  )}
                  {r.resolvedAt && <p className="text-xs text-fg-3">Resolved {formatDateTime(r.resolvedAt, timeZone)}</p>}
                </li>
              );
            })}
          </ul>
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
      {resolving && (
        <ResolveDialog
          report={resolving}
          onClose={() => setResolving(null)}
          onResolved={() => {
            setResolving(null);
            res.reload();
          }}
        />
      )}
    </Panel>
  );
}

function Conversations() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const [status, setStatus] = useState<'all' | 'open' | 'closed' | 'blocked'>('all');
  const [offset, setOffset] = useState(0);
  const res = useResource(`admin:convs:${status}:${offset}`, (signal) =>
    services.admin.conversations({ limit: PAGE, offset, ...(status !== 'all' ? { status } : {}) }, { signal }),
  );
  const when = (v: unknown) => (typeof v === 'string' && Number.isFinite(Date.parse(v)) ? formatDateTime(Date.parse(v), timeZone) : MISSING);

  return (
    <Panel
      title="Expert conversations"
      meta={<span>Admins can read any conversation through the normal chat endpoints</span>}
      actions={
        <SegmentedControl
          label="Conversation status"
          value={status}
          onChange={(v) => {
            setOffset(0);
            setStatus(v);
          }}
          options={[
            { value: 'all', label: 'All' },
            { value: 'open', label: 'Open' },
            { value: 'closed', label: 'Closed' },
            { value: 'blocked', label: 'Blocked' },
          ]}
        />
      }
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading conversations">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title="No conversations" />
      ) : (
        <>
          <TableRegion label="Expert conversations">
            <thead>
              <tr>
                <Th>Expert</Th>
                <Th>Subscriber</Th>
                <Th>Status</Th>
                <Th>Blocked by</Th>
                <Th>Last message</Th>
                <Th>Started</Th>
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((c, i) => {
                const st = text(c.status);
                return (
                  <tr key={typeof c.id === 'string' ? c.id : i}>
                    <Td>{text(rec(c.expert)?.display_name)}</Td>
                    <Td>{text(rec(c.user)?.display_name)}</Td>
                    <Td>
                      <Badge tone={st === 'blocked' ? 'danger' : st === 'open' ? 'up' : 'neutral'}>{st}</Badge>
                    </Td>
                    <Td>{text(c.blocked_by)}</Td>
                    <Td className="text-fg-2">{when(c.last_message_at)}</Td>
                    <Td className="text-fg-2">{when(c.created_at)}</Td>
                  </tr>
                );
              })}
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
    </Panel>
  );
}

/** Admin › Moderation: user reports (hide or dismiss) and expert conversations. */
export function AdminModerationPage() {
  return (
    <div className="flex flex-col gap-5">
      <Reports />
      <Conversations />
    </div>
  );
}
