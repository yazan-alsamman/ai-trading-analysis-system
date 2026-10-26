import { FastForward, Undo2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Field, FormError, Input, Select } from '@/components/ui/Form';
import { JsonView } from '@/components/ui/JsonView';
import { Panel, Stat } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminInvoice, AdminSubscription, JsonObject } from '@/domain/admin';
import { useResource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';

const SUB_PAGE = 25;
const STATUSES = ['trialing', 'active', 'past_due', 'canceled', 'expired'] as const;
const STATUS_TONE: Record<string, BadgeTone> = { trialing: 'info', active: 'up', past_due: 'warning', canceled: 'neutral', expired: 'neutral' };

const isObj = (v: unknown): v is JsonObject => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown) => (typeof v === 'string' || typeof v === 'number' ? String(v) : '—');

function StatsPanel() {
  const services = useServices();
  const res = useResource('admin:payment-stats', (signal) => services.admin.paymentStats({ signal }));
  const s = res.data;
  const inv = s?.invoices;
  const sub = s?.subscriptions;
  const invoices = isObj(inv) ? inv : null;
  const subs = isObj(sub) ? sub : null;
  return (
    <Panel title="Payment statistics" meta={<Badge tone="demo">Demo payments: no real money</Badge>}>
      {res.status === 'loading' ? (
        <Loading label="Loading payment statistics">
          <SkeletonRows rows={3} />
        </Loading>
      ) : res.status === 'error' || !s ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : (
        <div className="flex flex-col gap-5">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="MRR" value={<span className="num">{str(s.mrr)}</span>} />
            <Stat label="Platform fees" value={<span className="num">{str(s.platform_fees)}</span>} />
          </dl>
          {invoices && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-fg">Invoices</h3>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {Object.entries(invoices).map(([status, v]) => (
                  <Stat key={status} label={status} value={<span className="num">{isObj(v) ? str(v.count) : str(v)}</span>} hint={isObj(v) ? `Amount ${str(v.amount)}` : undefined} />
                ))}
              </dl>
            </div>
          )}
          {subs && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-fg">Subscriptions</h3>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {Object.entries(subs).map(([status, v]) => (
                  <Stat key={status} label={status.replace('_', ' ')} value={<span className="num">{str(v)}</span>} />
                ))}
              </dl>
            </div>
          )}
          {(!invoices || !subs) && <JsonView value={s} />}
        </div>
      )}
    </Panel>
  );
}

function SubscriptionsPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [ff, setFf] = useState<{ sub: AdminSubscription; to: 'period_end' | 'grace_end' } | null>(null);
  const [busy, setBusy] = useState(false);
  const res = useResource(`admin:subs:${status}:${offset}`, (signal) => services.admin.subscriptions({ limit: SUB_PAGE, offset, ...(status ? { status } : {}) }, { signal }));

  const fastForward = async () => {
    if (!ff) return;
    setBusy(true);
    try {
      const r = await services.admin.fastForward(ff.sub.id, ff.to);
      res.setData((p) => ({ total: p?.total ?? 0, items: (p?.items ?? []).map((x) => (x.id === r.subscription.id ? r.subscription : x)) }));
      notify(`Fast-forwarded: ${r.outcome}.`, 'success');
      setFf(null);
    } catch (e) {
      notify(isApiError(e) && e.kind === 'forbidden' ? 'Demo tools are disabled on this server (PAYMENT_DEMO_TOOLS is off).' : userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Subscriptions" meta={<span>Expert subscriptions on the demo payment provider</span>} flush>
      <div className="border-b border-line px-4 py-3">
        <Field label="Status" className="w-full sm:w-44">
          {({ id }) => (
            <Select
              id={id}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ')}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      {res.status === 'loading' ? (
        <Loading label="Loading subscriptions">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title="No subscriptions" />
      ) : (
        <>
          <TableRegion label="Subscriptions (admin)">
            <thead>
              <tr>
                <Th>Subscriber</Th>
                <Th>Expert</Th>
                <Th numeric>Price</Th>
                <Th>Status</Th>
                <Th>Period end</Th>
                <Th>Past due since</Th>
                <Th>Ended</Th>
                <Th>
                  <span className="sr-only">Demo tools</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((s) => (
                <tr key={s.id}>
                  <Td>{s.user.name}</Td>
                  <Td>{s.expert.name}</Td>
                  <Td numeric>
                    {s.price} {s.currency}/{s.interval}
                  </Td>
                  <Td>
                    <Badge tone={STATUS_TONE[s.status] ?? 'neutral'}>{s.status.replace('_', ' ')}</Badge>
                    {s.cancelAtPeriodEnd && <span className="ml-1.5 text-xs text-fg-3">ends at period end</span>}
                  </Td>
                  <Td className="text-fg-2">{formatDate(s.currentPeriodEnd, timeZone)}</Td>
                  <Td className="text-fg-2">{s.pastDueSince ? formatDate(s.pastDueSince, timeZone) : '—'}</Td>
                  <Td className="text-fg-2">{s.endedAt ? formatDate(s.endedAt, timeZone) : '—'}</Td>
                  <Td>
                    {!s.endedAt && (
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" icon={FastForward} onClick={() => setFf({ sub: s, to: 'period_end' })}>
                          End period
                        </Button>
                        {s.status === 'past_due' && (
                          <Button size="sm" variant="ghost" onClick={() => setFf({ sub: s, to: 'grace_end' })}>
                            End grace
                          </Button>
                        )}
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
          {res.data.total > SUB_PAGE && (
            <div className="flex justify-end gap-2 border-t border-line px-4 py-2">
              <Button size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - SUB_PAGE))}>
                Previous
              </Button>
              <Button size="sm" disabled={offset + SUB_PAGE >= res.data.total} onClick={() => setOffset((o) => o + SUB_PAGE)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
      <ConfirmDialog
        open={ff !== null}
        title={ff?.to === 'grace_end' ? 'End the grace period now?' : 'End the current period now?'}
        description={`DEMO tool: processes ${ff?.sub.user.name ?? ''}'s subscription as the hourly task would at ${ff?.to === 'grace_end' ? 'the end of the grace period' : 'the end of the period'} (renewal with the demo card, or expiry). Disabled on servers without demo tools.`}
        confirmLabel="Fast-forward"
        busy={busy}
        onConfirm={() => void fastForward()}
        onCancel={() => setFf(null)}
      />
    </Panel>
  );
}

function RefundPanel() {
  const services = useServices();
  const [invoiceId, setInvoiceId] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<AdminInvoice | null>(null);
  const valid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(invoiceId.trim());

  const refund = async () => {
    setBusy(true);
    setError(null);
    try {
      setDone(await services.admin.refundInvoice(invoiceId.trim()));
      setInvoiceId('');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  };

  return (
    <Panel title="Refund an invoice" meta={<Badge tone="demo">Demo payments: no real money</Badge>}>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) setConfirm(true);
        }}
      >
        <Field label="Invoice id" hint="The backend has no admin invoice list: take the id from the subscriber's invoice." className="w-full sm:w-96">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={invoiceId} invalid={invoiceId !== '' && !valid} onChange={(e) => setInvoiceId(e.target.value)} placeholder="00000000-0000-0000-0000-000000000000" />}
        </Field>
        <Button type="submit" icon={Undo2} disabled={!valid}>
          Refund
        </Button>
      </form>
      <div className="mt-3">
        <FormError message={error} />
      </div>
      {done && (
        <p role="status" className="mt-3 text-sm text-fg-2">
          Invoice {done.number} ({done.amount} {done.currency}) is now {done.status}.
        </p>
      )}
      <ConfirmDialog
        open={confirm}
        title="Refund this invoice?"
        description="The paid invoice is refunded (demo) and its subscription ends now. Only a paid invoice can be refunded."
        confirmLabel="Refund"
        busy={busy}
        onConfirm={() => void refund()}
        onCancel={() => setConfirm(false)}
      />
    </Panel>
  );
}

/** Admin › Payments: statistics, subscriptions, demo tools and refunds (DEMO payment provider only). */
export function AdminPaymentsPage() {
  return (
    <div className="flex flex-col gap-5">
      <p className="rounded-md border border-dashed border-demo/50 bg-demo-soft px-3 py-2 text-sm text-fg">
        Payments on this platform use the backend&apos;s demo provider: test cards only, no real money moves.
      </p>
      <StatsPanel />
      <SubscriptionsPanel />
      <RefundPanel />
    </div>
  );
}
