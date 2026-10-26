import { Pencil, Plus, Save, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge, DemoBadge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select, Switch, Textarea } from '@/components/ui/Form';
import { Panel, Stat } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { EXPERT_LANGUAGES, EXPERT_MARKETS, type ExpertPlan, type ExpertProfile, type PlanInput, type PlanInterval, type PlanPerks } from '@/domain/social';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatPct, MISSING } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { perksText, priceText } from './subscriptionText';

const PRICE = /^\d+(\.\d{1,2})?$/;
const LANGUAGE_LABELS: Record<string, string> = { en: 'English', ar: 'Arabic', fr: 'French', de: 'German', es: 'Spanish', tr: 'Turkish' };
const EMPTY_PROFILE: ExpertProfile = { headline: '', bio: '', markets: [], languages: [], chatEnabled: true, responseTimeHint: null, isListed: true };

const toggleIn = (list: string[], value: string, on: boolean) => (on ? [...new Set([...list, value])] : list.filter((v) => v !== value));

function ProfileForm({ initial, exists, onSaved }: { initial: ExpertProfile; exists: boolean; onSaved: (p: ExpertProfile) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [headlineError, setHeadlineError] = useState<string | undefined>();
  const [saving, setSaving] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);

  const save = async () => {
    const headline = draft.headline.trim();
    if (!headline || headline.length > 120) return setHeadlineError('Write a one-line headline (1–120 characters).');
    setHeadlineError(undefined);
    setError(null);
    setSaving(true);
    try {
      const saved = await services.expertStudio.saveProfile({ ...draft, headline });
      onSaved(saved);
      notify(exists ? 'Expert profile saved.' : 'Expert profile created.', 'success');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      noValidate
      aria-label="Expert profile"
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      {!exists && <p className="text-sm text-fg-2">Create your expert profile to appear in the experts directory and offer subscription plans.</p>}
      <Field label="Headline" error={headlineError} hint="One line, e.g. “Gold swing trader, 10 years”.">
        {({ id, describedBy, invalid }) => (
          <Input id={id} aria-describedby={describedBy} invalid={invalid} maxLength={120} value={draft.headline} onChange={(e) => setDraft((d) => ({ ...d, headline: e.target.value }))} />
        )}
      </Field>
      <Field label="Bio" optional hint="Up to 5,000 characters. Describe your approach; do not promise returns.">
        {({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} rows={4} maxLength={5000} value={draft.bio} onChange={(e) => setDraft((d) => ({ ...d, bio: e.target.value }))} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Markets</legend>
          <div className="grid grid-cols-2 gap-2">
            {EXPERT_MARKETS.map((m) => (
              <Checkbox key={m} label={m.charAt(0).toUpperCase() + m.slice(1)} checked={draft.markets.includes(m)} onChange={(e) => setDraft((d) => ({ ...d, markets: toggleIn(d.markets, m, e.target.checked) }))} />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Languages</legend>
          <div className="grid grid-cols-2 gap-2">
            {EXPERT_LANGUAGES.map((l) => (
              <Checkbox key={l} label={LANGUAGE_LABELS[l] ?? l} checked={draft.languages.includes(l)} onChange={(e) => setDraft((d) => ({ ...d, languages: toggleIn(d.languages, l, e.target.checked) }))} />
            ))}
          </div>
        </fieldset>
      </div>
      <Switch checked={draft.chatEnabled} onChange={(v) => setDraft((d) => ({ ...d, chatEnabled: v }))} label="Accept chat" description="Subscribers whose plan includes chat can message you." />
      <Field label="Usual response time" optional hint="Shown to subscribers, e.g. “within a few hours”.">
        {({ id, describedBy }) => (
          <Input id={id} aria-describedby={describedBy} maxLength={60} value={draft.responseTimeHint ?? ''} onChange={(e) => setDraft((d) => ({ ...d, responseTimeHint: e.target.value || null }))} />
        )}
      </Field>
      <Switch checked={draft.isListed} onChange={(v) => setDraft((d) => ({ ...d, isListed: v }))} label="Listed in the experts directory" description="Unlisted profiles keep their subscribers but are hidden from the directory." />
      <FormError message={error} />
      <Button type="submit" variant="primary" icon={Save} className="self-start" loading={saving} disabled={exists && !dirty}>
        {exists ? 'Save profile' : 'Create expert profile'}
      </Button>
    </form>
  );
}

const EMPTY_PLAN: PlanInput = {
  name: '',
  description: '',
  price: '',
  currency: 'USD',
  interval: 'month',
  trialDays: 0,
  perks: { premiumPosts: true, chat: false, signalsFeed: false },
  isActive: true,
};

function PlanDialog({ open, editing, onClose, onSaved }: { open: boolean; editing: ExpertPlan | null; onClose: () => void; onSaved: (plan: ExpertPlan) => void }) {
  const services = useServices();
  const [draft, setDraft] = useState<PlanInput>(EMPTY_PLAN);
  const [errors, setErrors] = useState<{ name?: string; price?: string; trial?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastOpen, setLastOpen] = useState(false);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) {
      setDraft(
        editing
          ? {
              name: editing.name,
              description: editing.description,
              price: editing.price,
              currency: editing.currency === 'EUR' ? 'EUR' : 'USD',
              interval: editing.interval,
              trialDays: editing.trialDays,
              perks: editing.perks,
              isActive: editing.isActive,
            }
          : EMPTY_PLAN,
      );
      setErrors({});
      setFormError(null);
    }
  }

  const setPerk = (key: keyof PlanPerks, on: boolean) => setDraft((d) => ({ ...d, perks: { ...d.perks, [key]: on } }));

  const submit = async () => {
    const next: typeof errors = {};
    const name = draft.name.trim();
    if (!name || name.length > 60) next.name = 'Name the plan (1–60 characters).';
    if (!PRICE.test(draft.price) || Number(draft.price) > 100_000) next.price = 'Enter a price like 19 or 19.99 (at most 100,000).';
    if (!Number.isInteger(draft.trialDays) || draft.trialDays < 0 || draft.trialDays > 30) next.trial = 'Trial days must be 0–30.';
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true);
    setFormError(null);
    try {
      const saved = editing
        ? await services.expertStudio.updatePlan(editing.id, {
            name,
            description: draft.description,
            price: draft.price,
            trialDays: draft.trialDays,
            perks: draft.perks,
            isActive: draft.isActive,
          })
        : await services.expertStudio.createPlan({ ...draft, name });
      onSaved(saved);
    } catch (e) {
      setFormError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? `Edit “${editing.name}”` : 'New subscription plan'}
      description={editing ? 'A new price applies to new subscriptions and renewals only.' : 'Payments on this server are simulated (demo): no real money moves.'}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="plan-form" loading={busy}>
            {editing ? 'Save plan' : 'Create plan'}
          </Button>
        </>
      }
    >
      <form
        id="plan-form"
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <FormError message={formError} />
        <Field label="Name" error={errors.name}>
          {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} maxLength={60} value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} />}
        </Field>
        <Field label="Description" optional>
          {({ id, describedBy }) => (
            <Textarea id={id} aria-describedby={describedBy} rows={3} maxLength={1000} value={draft.description} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Price" error={errors.price}>
            {({ id, describedBy, invalid }) => (
              <Input id={id} aria-describedby={describedBy} invalid={invalid} inputMode="decimal" placeholder="19.00" value={draft.price} onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value.trim() }))} />
            )}
          </Field>
          <Field label="Currency" hint={editing ? 'Fixed after creation.' : undefined}>
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} disabled={!!editing} value={draft.currency} onChange={(e) => setDraft((d) => ({ ...d, currency: e.target.value === 'EUR' ? 'EUR' : 'USD' }))}>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </Select>
            )}
          </Field>
          <Field label="Billing" hint={editing ? 'Fixed after creation.' : undefined}>
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} disabled={!!editing} value={draft.interval} onChange={(e) => setDraft((d) => ({ ...d, interval: e.target.value as PlanInterval }))}>
                <option value="month">Monthly</option>
                <option value="year">Yearly</option>
              </Select>
            )}
          </Field>
        </div>
        <Field label="Free trial (days)" error={errors.trial} className="max-w-40">
          {({ id, describedBy, invalid }) => (
            <Input id={id} aria-describedby={describedBy} invalid={invalid} type="number" min={0} max={30} value={draft.trialDays} onChange={(e) => setDraft((d) => ({ ...d, trialDays: Math.round(Number(e.target.value) || 0) }))} />
          )}
        </Field>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-fg">Included</legend>
          <Checkbox label="Premium posts" checked={draft.perks.premiumPosts} onChange={(e) => setPerk('premiumPosts', e.target.checked)} />
          <Checkbox label="Chat with you" checked={draft.perks.chat} onChange={(e) => setPerk('chat', e.target.checked)} />
          <Checkbox label="Your signal feed" checked={draft.perks.signalsFeed} onChange={(e) => setPerk('signalsFeed', e.target.checked)} />
        </fieldset>
        <Switch checked={draft.isActive} onChange={(v) => setDraft((d) => ({ ...d, isActive: v }))} label="Open for new subscribers" />
      </form>
    </Dialog>
  );
}

function PlansPanel() {
  const services = useServices();
  const { notify } = useToast();
  const plans = useResource('expert-plans', (signal) => services.expertStudio.listPlans({ signal }));
  const [dialog, setDialog] = useState<{ editing: ExpertPlan | null } | null>(null);
  const [deactivating, setDeactivating] = useState<ExpertPlan | null>(null);
  const [busy, setBusy] = useState(false);

  const deactivate = async () => {
    if (!deactivating) return;
    setBusy(true);
    try {
      await services.expertStudio.deactivatePlan(deactivating.id);
      plans.reload();
      notify(`Plan “${deactivating.name}” closed to new subscribers.`, 'info');
      setDeactivating(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-medium text-fg">Subscription plans</h3>
        <Button size="sm" icon={Plus} className="ml-auto" onClick={() => setDialog({ editing: null })}>
          New plan
        </Button>
      </div>
      {plans.status === 'loading' ? (
        <Loading label="Loading plans">
          <SkeletonRows rows={2} />
        </Loading>
      ) : plans.status === 'error' && !plans.data ? (
        <ErrorState error={plans.error} onRetry={plans.reload} compact />
      ) : (plans.data?.length ?? 0) === 0 ? (
        <EmptyState compact title="No plans yet" description="Create a plan so traders can subscribe to you." />
      ) : (
        <ul className="divide-y divide-line rounded-md border border-line">
          {(plans.data ?? []).map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium text-fg">
                  {p.name} {p.isActive ? <Badge tone="up">Open</Badge> : <Badge>Closed</Badge>}
                </p>
                <p className="num text-xs text-fg-3">
                  {priceText(p.price, p.currency, p.interval)}
                  {p.trialDays > 0 && ` · ${p.trialDays}-day trial`} · {perksText(p.perks)}
                </p>
              </div>
              <IconButton icon={Pencil} label={`Edit ${p.name}`} size="sm" onClick={() => setDialog({ editing: p })} tooltipSide="left" />
              {p.isActive && <IconButton icon={Trash2} label={`Close ${p.name} to new subscribers`} size="sm" onClick={() => setDeactivating(p)} tooltipSide="left" />}
            </li>
          ))}
        </ul>
      )}
      <PlanDialog
        open={dialog !== null}
        editing={dialog?.editing ?? null}
        onClose={() => setDialog(null)}
        onSaved={(plan) => {
          plans.setData((list) => {
            const current = list ?? [];
            return current.some((x) => x.id === plan.id) ? current.map((x) => (x.id === plan.id ? plan : x)) : [...current, plan];
          });
          notify(dialog?.editing ? 'Plan saved.' : 'Plan created.', 'success');
          setDialog(null);
        }}
      />
      <ConfirmDialog
        open={deactivating !== null}
        title="Close this plan?"
        description={`“${deactivating?.name ?? ''}” will no longer accept new subscribers. Existing subscribers keep it until they cancel.`}
        confirmLabel="Close plan"
        busy={busy}
        onConfirm={deactivate}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}

function EarningsPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const earnings = useResource('expert-earnings', (signal) => services.expertStudio.earnings({ signal }));
  const e = earnings.data;

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-fg">Earnings</h3>
      {earnings.status === 'loading' ? (
        <Loading label="Loading earnings">
          <SkeletonRows rows={3} />
        </Loading>
      ) : !e ? (
        <ErrorState error={earnings.error} onRetry={earnings.reload} compact />
      ) : (
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Active subscribers" value={<span className="num">{e.activeSubscribers}</span>} />
            <Stat label="Monthly recurring" value={<span className="num">{`${e.mrr} ${e.currency}`}</span>} />
            <Stat label="Churn (30 days)" value={<span className="num">{formatPct(e.churn30dPct, 1)}</span>} />
            <Stat label="Platform fee" value={<span className="num">{formatPct(e.platformFeePct, 1)}</span>} />
          </dl>
          {e.months.length > 0 && (
            <TableRegion label="Earnings per month" className="rounded-md border border-line">
              <thead>
                <tr>
                  <Th>Month</Th>
                  <Th numeric>Gross</Th>
                  <Th numeric>Platform fee</Th>
                  <Th numeric>Net</Th>
                  <Th numeric>Refunded</Th>
                  <Th numeric>Invoices</Th>
                </tr>
              </thead>
              <tbody>
                {e.months.map((m) => (
                  <tr key={m.month}>
                    <Td className="num">{m.month}</Td>
                    <Td numeric>{m.gross}</Td>
                    <Td numeric className="text-fg-2">
                      {m.platformFee}
                    </Td>
                    <Td numeric>{m.net}</Td>
                    <Td numeric className="text-fg-2">
                      {m.refunded}
                    </Td>
                    <Td numeric>{m.invoices}</Td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
          )}
          {e.recentInvoices.length > 0 && (
            <TableRegion label="Recent invoices" className="rounded-md border border-line">
              <thead>
                <tr>
                  <Th>Invoice</Th>
                  <Th>Subscriber</Th>
                  <Th>Plan</Th>
                  <Th numeric>Amount</Th>
                  <Th>Status</Th>
                  <Th>Paid</Th>
                </tr>
              </thead>
              <tbody>
                {e.recentInvoices.map((i) => (
                  <tr key={i.number}>
                    <Td className="num">{i.number}</Td>
                    <Td>{i.subscriber}</Td>
                    <Td className="text-fg-2">{i.plan}</Td>
                    <Td numeric>
                      {i.amount} {i.currency}
                    </Td>
                    <Td>{i.status}</Td>
                    <Td className="num text-fg-2">{i.paidAt ? formatDate(i.paidAt, timeZone) : MISSING}</Td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
          )}
        </div>
      )}
    </div>
  );
}

/** Backend mode, experts only: profile, plans and earnings (/me/expert-profile, /me/plans, /me/earnings). */
export function ExpertStudioSection() {
  const services = useServices();
  const profile = useResource('expert-profile', (signal) => services.expertStudio.getProfile({ signal }));

  return (
    <div id="expert" className="scroll-mt-4">
      <Panel title="Expert studio" meta={<DemoBadge label="Demo payments" detail="Subscriptions are paid through the backend's demo provider: no real money moves." />}>
        {profile.status === 'loading' ? (
          <Loading label="Loading expert profile">
            <SkeletonRows rows={4} />
          </Loading>
        ) : profile.status === 'error' ? (
          <ErrorState error={profile.error} onRetry={profile.reload} compact />
        ) : (
          <div className="flex flex-col gap-8">
            <ProfileForm
              key={profile.data ? 'existing' : 'new'}
              initial={profile.data ?? EMPTY_PROFILE}
              exists={profile.data !== null && profile.data !== undefined}
              onSaved={(p) => profile.setData(() => p)}
            />
            {profile.data && (
              <>
                <PlansPanel />
                <EarningsPanel />
              </>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
