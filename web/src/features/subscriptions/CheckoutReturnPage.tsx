import { CheckCircle2, CircleHelp, XCircle } from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { SubscriptionStatus } from '@/domain/social';
import { DemoPaymentNotice } from '@/features/community/ExpertDetailPage';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatDate } from '@/lib/format';

const SUBSCRIPTION_STATUS: Record<SubscriptionStatus, { label: string; tone: BadgeTone }> = {
  trialing: { label: 'Trial', tone: 'info' },
  active: { label: 'Active', tone: 'up' },
  past_due: { label: 'Payment failed', tone: 'warning' },
  canceled: { label: 'Canceled', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'neutral' },
};

const OUTCOME = {
  succeeded: { icon: CheckCircle2, tone: 'text-up', title: 'Payment accepted', body: 'Your subscription is being activated. It can take a few seconds to appear below.' },
  failed: { icon: XCircle, tone: 'text-danger', title: 'Payment declined', body: 'The test card was declined, so no subscription was started. You can try again from the expert’s page.' },
  unknown: { icon: CircleHelp, tone: 'text-fg-3', title: 'Checkout finished', body: 'The checkout did not report a result. Check your subscriptions below.' },
} as const;

/**
 * Where the backend's DEMO checkout sends the browser back
 * (`?checkout_id=…&status=succeeded|failed`, docs/subscriptions.md).
 * The result shown comes from the server's subscription list, not the URL.
 */
export function CheckoutReturnPage() {
  usePageTitle('Subscription checkout');
  const services = useServices();
  const { timeZone } = usePreferences();
  const [params] = useSearchParams();
  const status = params.get('status');
  const outcome = OUTCOME[status === 'succeeded' || status === 'failed' ? status : 'unknown'];
  const Icon = outcome.icon;
  const subs = useResource(`subscriptions:${params.get('checkout_id') ?? ''}`, (signal) => services.social.subscriptions({ signal }));

  return (
    <Page width="reading">
      <PageHeader title="Subscription checkout" description="The result of your demo payment." />

      <section aria-live="polite" className="flex items-start gap-3 rounded-lg border border-line bg-surface p-4">
        <Icon aria-hidden className={cn('mt-0.5 size-5 shrink-0', outcome.tone)} />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-fg">{outcome.title}</h2>
          <p className="mt-0.5 text-sm text-fg-2">{outcome.body}</p>
        </div>
      </section>
      <DemoPaymentNotice />

      <Panel
        title="Your subscriptions"
        actions={
          <button type="button" onClick={subs.reload} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
            Refresh
          </button>
        }
        flush
      >
        {subs.status === 'loading' ? (
          <Loading label="Loading subscriptions">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : subs.status === 'error' && !subs.data ? (
          <ErrorState error={subs.error} onRetry={subs.reload} compact />
        ) : !subs.data?.length ? (
          <EmptyState title="No subscriptions yet" description="If you just paid, refresh in a few seconds." compact />
        ) : (
          <ul className="divide-y divide-line">
            {subs.data.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                    {s.expert.name} · {s.planName}
                    <Badge tone={SUBSCRIPTION_STATUS[s.status].tone}>{SUBSCRIPTION_STATUS[s.status].label}</Badge>
                    {s.cancelAtPeriodEnd && <Badge tone="warning">Ends at period end</Badge>}
                  </p>
                  <p className="text-xs text-fg-3">
                    <span className="num">
                      {s.price} {s.currency}
                    </span>{' '}
                    / {s.interval} · {s.cancelAtPeriodEnd || s.status === 'canceled' ? 'Access until' : 'Renews'} {formatDate(s.currentPeriodEnd, timeZone)}
                  </p>
                </div>
                <Link to={`/community/experts/${s.expert.id}`} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
                  Expert page
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="flex flex-wrap gap-2">
        <Link to="/settings#subscriptions" className={buttonClasses({ variant: 'primary' })}>
          Manage subscriptions
        </Link>
        <Link to="/community/experts" className={buttonClasses({ variant: 'secondary' })}>
          Back to experts
        </Link>
      </div>
    </Page>
  );
}
