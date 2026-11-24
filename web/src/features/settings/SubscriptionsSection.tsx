import { ChevronDown, ChevronRight, CreditCard } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge, DemoBadge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { Subscription, SubscriptionStatus } from '@/domain/social';
import { useResource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { perksText, priceText } from './subscriptionText';

const STATUS: Record<SubscriptionStatus, { label: string; tone: BadgeTone }> = {
  trialing: { label: 'Trial', tone: 'info' },
  active: { label: 'Active', tone: 'up' },
  past_due: { label: 'Payment due', tone: 'warning' },
  canceled: { label: 'Canceled', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'neutral' },
};

function SubscriptionRow({ sub, onChange }: { sub: Subscription; onChange: (s: Subscription) => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const status = STATUS[sub.status];
  const live = sub.status === 'active' || sub.status === 'trialing' || sub.status === 'past_due';

  const run = async (action: 'cancel' | 'resume') => {
    setBusy(true);
    try {
      const updated = action === 'cancel' ? await services.social.cancelSubscription(sub.id) : await services.social.resumeSubscription(sub.id);
      onChange(updated);
      notify(action === 'cancel' ? 'Subscription will end at the close of the current period.' : 'Subscription resumed.', 'success');
      setConfirm(false);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
            <Link to={`/community/experts/${sub.expert.id}`} className="hover:underline">
              {sub.expert.name}
            </Link>
            <span className="font-normal text-fg-2">· {sub.planName}</span>
            <Badge tone={status.tone}>{status.label}</Badge>
            {sub.cancelAtPeriodEnd && live && <Badge tone="warning">Ends {formatDate(sub.currentPeriodEnd, timeZone)}</Badge>}
          </p>
          <p className="num mt-0.5 text-xs text-fg-3">
            {priceText(sub.price, sub.currency, sub.interval)} · {perksText(sub.perks)}
          </p>
          <dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-xs text-fg-2">
            {live && (
              <div className="flex gap-1">
                <dt className="text-fg-3">Paid until</dt>
                <dd className="num">{formatDate(sub.currentPeriodEnd, timeZone)}</dd>
              </div>
            )}
            {sub.nextChargeAt && !sub.cancelAtPeriodEnd && (
              <div className="flex gap-1">
                <dt className="text-fg-3">Next charge</dt>
                <dd className="num">{formatDate(sub.nextChargeAt, timeZone)}</dd>
              </div>
            )}
            {sub.graceEndsAt && (
              <div className="flex gap-1">
                <dt className="text-fg-3">Grace period ends</dt>
                <dd className="num text-warning">{formatDate(sub.graceEndsAt, timeZone)}</dd>
              </div>
            )}
            {sub.endedAt && (
              <div className="flex gap-1">
                <dt className="text-fg-3">Ended</dt>
                <dd className="num">{formatDate(sub.endedAt, timeZone)}</dd>
              </div>
            )}
            {sub.paymentMethod?.last4 && (
              <div className="flex items-center gap-1">
                <dt className="sr-only">Card</dt>
                <CreditCard aria-hidden className="size-3.5 text-fg-3" />
                <dd>
                  {sub.paymentMethod.brand ?? 'Card'} ···· {sub.paymentMethod.last4} (demo)
                </dd>
              </div>
            )}
          </dl>
        </div>
        {live &&
          (sub.cancelAtPeriodEnd ? (
            <Button size="sm" loading={busy} onClick={() => run('resume')}>
              Resume
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirm(true)}>
              Cancel subscription
            </Button>
          ))}
      </div>
      {sub.invoices.length > 0 && (
        <div className="mt-2">
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-1 text-xs font-medium text-fg-2 hover:text-fg">
            {open ? <ChevronDown aria-hidden className="size-3.5" /> : <ChevronRight aria-hidden className="size-3.5" />}
            Invoices ({sub.invoices.length})
          </button>
          {open && (
            <TableRegion label={`Invoices for ${sub.expert.name}`} className="mt-2 rounded-md border border-line">
              <thead>
                <tr>
                  <Th>Number</Th>
                  <Th>Period</Th>
                  <Th numeric>Amount</Th>
                  <Th>Status</Th>
                  <Th>Paid</Th>
                </tr>
              </thead>
              <tbody>
                {sub.invoices.map((inv) => (
                  <tr key={inv.id}>
                    <Td className="num">{inv.number}</Td>
                    <Td className="num text-fg-2">
                      {formatDate(inv.periodStart, timeZone)} – {formatDate(inv.periodEnd, timeZone)}
                    </Td>
                    <Td numeric>
                      {inv.amount} {inv.currency}
                    </Td>
                    <Td>
                      {inv.status}
                      {inv.failureReason && <span className="block text-xs text-danger">{inv.failureReason}</span>}
                    </Td>
                    <Td className="num text-fg-2">{inv.refundedAt ? `Refunded ${formatDate(inv.refundedAt, timeZone)}` : formatDate(inv.paidAt, timeZone)}</Td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title="Cancel subscription?"
        description={`You keep access to ${sub.expert.name} until ${formatDate(sub.currentPeriodEnd, timeZone)}; it will not renew after that. You can resume before then.`}
        confirmLabel="Cancel at period end"
        busy={busy}
        onConfirm={() => run('cancel')}
        onCancel={() => setConfirm(false)}
      />
    </li>
  );
}

/** Backend mode: the user's expert subscriptions (docs/subscriptions.md). Payments are demo only. */
export function SubscriptionsSection() {
  const services = useServices();
  const subs = useResource('subscriptions', (signal) => services.social.subscriptions({ signal }));

  return (
    <div id="subscriptions" className="scroll-mt-4">
      <Panel
        title="Expert subscriptions"
        meta={<DemoBadge label="Demo payments" detail="Payments on this server are simulated: no real card is charged and no money moves." />}
        actions={
          <Link to="/community/experts" className="text-sm text-accent underline-offset-2 hover:underline">
            Browse experts
          </Link>
        }
        flush
      >
        {subs.status === 'loading' ? (
          <Loading label="Loading subscriptions">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : subs.status === 'error' && !subs.data ? (
          <ErrorState error={subs.error} onRetry={subs.reload} compact />
        ) : (subs.data?.length ?? 0) === 0 ? (
          <EmptyState compact title="No subscriptions" description="Subscribe to an expert for premium posts, chat or their signal feed." />
        ) : (
          <ul className="divide-y divide-line">
            {(subs.data ?? []).map((s) => (
              <SubscriptionRow key={s.id} sub={s} onChange={(u) => subs.setData((list) => (list ?? []).map((x) => (x.id === u.id ? u : x)))} />
            ))}
          </ul>
        )}
        <p className="border-t border-line px-4 py-2.5 text-xs text-fg-3">Demo payment provider: no real money is charged. Subscriptions give access to an expert’s content, never trade execution.</p>
      </Panel>
    </div>
  );
}
