import { ArrowLeft, CreditCard, FlaskConical } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { Panel, Stat } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, Skeleton, SkeletonRows } from '@/components/ui/StateViews';
import type { ExpertPlan } from '@/domain/social';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatNumber } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';
import { displayValue, humanizeKey } from './socialFormat';

const PERK_LABELS: { key: keyof ExpertPlan['perks']; label: string }[] = [
  { key: 'premiumPosts', label: 'Subscriber posts' },
  { key: 'chat', label: 'Chat with the expert' },
  { key: 'signalsFeed', label: 'Signal feed' },
];

/** The backend's payments are a test checkout: say so wherever money appears. */
export function DemoPaymentNotice() {
  return (
    <p className="flex items-start gap-2 rounded-md border border-dashed border-demo/50 bg-demo-soft px-3 py-2 text-xs text-fg">
      <FlaskConical aria-hidden className="mt-0.5 size-3.5 shrink-0 text-demo" />
      <span>
        <strong className="font-semibold">Demo payment</strong> — the backend’s test checkout, no real money is charged (test card{' '}
        <span className="num">4242 4242 4242 4242</span>, any future expiry, any 3-digit CVC).
      </span>
    </p>
  );
}

function SignalFeed({ expertId }: { expertId: string }) {
  const services = useServices();
  const res = useResource(`expert-signals:${expertId}`, (signal) => services.social.expertSignals(expertId, { signal }));

  return (
    <Panel title="Signal feed" meta={<span>Published by the expert for subscribers</span>} flush>
      {res.status === 'loading' ? (
        <Loading label="Loading signals">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        isApiError(res.error) && res.error.kind === 'forbidden' ? (
          <EmptyState title="Not included in your plan" description="Your subscription does not include the expert’s signal feed. Plans with the “Signal feed” perk do." compact />
        ) : (
          <ErrorState error={res.error} onRetry={res.reload} compact />
        )
      ) : !res.data?.length ? (
        <EmptyState title="No signals yet" description="Signals the expert publishes will appear here." compact />
      ) : (
        <ul className="divide-y divide-line">
          {res.data.map((s, i) => (
            <li key={typeof s.id === 'string' ? s.id : i} className="px-4 py-3">
              <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[160px_1fr]">
                {Object.entries(s).map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="text-xs text-fg-3">{humanizeKey(key)}</dt>
                    <dd className="min-w-0 break-words text-fg">{displayValue(value)}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** An expert's profile and subscription plans (backend: GET /experts/{id}, POST /subscriptions/checkout). */
export function ExpertDetailPage() {
  const { expertId = '' } = useParams();
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const res = useResource(`expert:${expertId}`, (signal) => services.social.expert(expertId, { signal }));
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  usePageTitle(res.data ? `${res.data.name} · Experts` : 'Expert');

  const back = (
    <Link to="/community/experts" className={buttonClasses({ variant: 'ghost', size: 'sm', className: 'self-start' })}>
      <ArrowLeft aria-hidden className="size-4" />
      Experts
    </Link>
  );

  if (res.status === 'loading')
    return (
      <Loading label="Loading expert">
        <Skeleton className="h-48 w-full" />
      </Loading>
    );
  if (res.status === 'error' && !res.data)
    return (
      <div className="flex flex-col gap-3">
        {back}
        {isApiError(res.error) && res.error.kind === 'not_found' ? (
          <EmptyState title="Expert not found" description="This expert is not listed (any more)." />
        ) : (
          <ErrorState error={res.error} onRetry={res.reload} title="Could not load the expert" />
        )}
      </div>
    );
  const e = res.data;
  if (!e) return null;
  const plans = e.plans.filter((p) => p.isActive);

  const subscribe = async (plan: ExpertPlan) => {
    setBusyPlan(plan.id);
    try {
      const checkout = await services.social.checkout(plan.id, `${window.location.origin}/subscriptions/return`);
      // The server's hosted checkout page; never follow a non-web URL.
      if (!/^https?:\/\//i.test(checkout.checkoutUrl)) {
        notify('The server returned an invalid checkout address.', 'danger');
        setBusyPlan(null);
        return;
      }
      window.location.assign(checkout.checkoutUrl);
    } catch (err) {
      notify(userMessage(err), 'danger');
      setBusyPlan(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {back}
      <section aria-labelledby="expert-name" className="rounded-lg border border-line bg-surface p-4">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 id="expert-name" className="flex flex-wrap items-center gap-2 text-lg font-semibold text-fg">
              {e.name}
              <Badge tone={e.chatEnabled ? 'accent' : 'neutral'}>{e.chatEnabled ? 'Chat open' : 'No chat'}</Badge>
              {e.isSubscribed && <Badge tone="up">Subscribed</Badge>}
            </h2>
            <p className="mt-0.5 text-sm text-fg-2">{e.headline}</p>
          </div>
        </div>
        {e.bio && <p className="mt-3 text-sm whitespace-pre-line text-fg">{e.bio}</p>}
        <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Followers" value={<span className="num">{formatNumber(e.followers)}</span>} />
          <Stat label="Subscribers" value={<span className="num">{formatNumber(e.subscribers)}</span>} />
          <Stat label="Member since" value={formatDate(e.memberSince, timeZone)} />
          <Stat label="Replies" value={e.chatEnabled ? (e.responseTimeHint ?? 'Not stated') : 'Chat closed'} />
        </dl>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {e.markets.map((m) => (
            <Badge key={m}>{m}</Badge>
          ))}
          {e.languages.map((l) => (
            <Badge key={l} tone="info">
              {l.toUpperCase()}
            </Badge>
          ))}
        </div>
      </section>

      <Panel title="Subscription plans" meta={<span>Set by the expert</span>}>
        <div className="flex flex-col gap-4">
          <DemoPaymentNotice />
          {plans.length === 0 ? (
            <EmptyState title="No plans offered" description="This expert has no active subscription plan right now." compact />
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {plans.map((plan) => (
                <li key={plan.id} className="flex flex-col gap-3 rounded-lg border border-line p-4">
                  <div>
                    <p className="text-sm font-semibold text-fg">{plan.name}</p>
                    <p className="mt-1 text-lg text-fg">
                      <span className="num">
                        {plan.price} {plan.currency}
                      </span>
                      <span className="text-sm text-fg-3"> / {plan.interval}</span>
                    </p>
                    {plan.trialDays > 0 && <p className="text-xs text-fg-3">{plan.trialDays}-day free trial</p>}
                  </div>
                  {plan.description && <p className="text-sm text-fg-2">{plan.description}</p>}
                  <ul aria-label={`${plan.name} includes`} className="flex flex-wrap gap-1.5">
                    {PERK_LABELS.filter((perk) => plan.perks[perk.key]).map((perk) => (
                      <li key={perk.key}>
                        <Badge tone="accent">{perk.label}</Badge>
                      </li>
                    ))}
                  </ul>
                  <Button
                    variant="primary"
                    icon={CreditCard}
                    className="mt-auto self-start"
                    loading={busyPlan === plan.id}
                    disabled={e.isSubscribed || (busyPlan !== null && busyPlan !== plan.id)}
                    title={e.isSubscribed ? 'You already subscribe to this expert (one subscription per expert).' : undefined}
                    onClick={() => void subscribe(plan)}
                  >
                    Subscribe (demo payment)
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {e.isSubscribed && (
            <p className="text-xs text-fg-3">
              Manage or cancel your subscription in{' '}
              <Link to="/settings#subscriptions" className="text-accent underline-offset-2 hover:underline">
                Settings → Subscriptions
              </Link>
              .
            </p>
          )}
        </div>
      </Panel>

      {e.isSubscribed && <SignalFeed expertId={e.id} />}
    </div>
  );
}
