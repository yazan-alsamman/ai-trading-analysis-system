import { Bot, ShieldAlert } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { Page, PageHeader } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument, isInstrumentSymbol } from '@/domain/instruments';
import { isTimeframe } from '@/domain/market';
import { computeTradeRisk, evaluateLimits, planFromOpportunity, remainingRiskCapacity, worstStatus, type LimitId } from '@/domain/risk';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn } from '@/lib/cn';
import { formatMoney, formatPct, formatPrice } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { LimitMeter } from './LimitMeter';
import { STATUS_META } from './limitStatus';
import { parseDecimal } from './parse';
import { ProfileForm } from './ProfileForm';
import { ServerCrossCheck, ServerProfileBanner } from './ServerRisk';
import { ServerRiskTemplates } from './ServerRiskTemplates';
import { TradePlanner, type PlannerState } from './TradePlanner';

const BINDING_LABEL: Record<LimitId, string> = {
  per_trade: 'per-trade limit',
  daily_loss: 'daily loss limit',
  open_risk: 'aggregate open-risk limit',
  positions: 'position count',
};

/** Planner state lives in the URL so "Size this trade" links can prefill it and the view can be shared. */
function usePlannerState(defaultRisk: number, fallbackSymbol: PlannerState['symbol']) {
  const [params, setParams] = useSearchParams();
  const symbol = params.get('symbol') ?? '';
  const tf = params.get('tf') ?? '';
  const state: PlannerState = {
    symbol: isInstrumentSymbol(symbol) ? symbol : fallbackSymbol,
    timeframe: isTimeframe(tf) ? tf : '1h',
    entry: params.get('entry') ?? '',
    stop: params.get('stop') ?? '',
    target: params.get('target') ?? '',
    risk: params.get('risk') ?? String(defaultRisk),
    rate: params.get('rate') ?? '',
    origin: params.get('origin') === 'model' ? 'model' : 'user',
  };
  const update = (patch: Partial<PlannerState>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        const keys: Record<keyof PlannerState, string> = { symbol: 'symbol', timeframe: 'tf', entry: 'entry', stop: 'stop', target: 'target', risk: 'risk', rate: 'rate', origin: 'origin' };
        for (const [k, v] of Object.entries(patch) as [keyof PlannerState, string][]) {
          if (v === '' || (k === 'origin' && v === 'user')) next.delete(keys[k]);
          else next.set(keys[k], v);
        }
        return next;
      },
      { replace: true },
    );
  return [state, update] as const;
}

function Cell({ label, children, hint, className }: { label: string; children: React.ReactNode; hint?: React.ReactNode; className?: string }) {
  return (
    <div className={cn('min-w-0 bg-surface px-4 py-3.5', className)}>
      <dt className="text-xs text-fg-3">{label}</dt>
      <dd className="num mt-1 truncate text-lg leading-tight text-fg">{children}</dd>
      {hint && <dd className="mt-1 truncate text-xs text-fg-3">{hint}</dd>}
    </div>
  );
}

export function RiskPage() {
  usePageTitle('Capital & risk');
  const services = useServices();
  const { prefs, activeWorkspace } = usePreferences();
  const profile = prefs.riskProfile;
  const [state, update] = usePlannerState(profile.maxRiskPerTradePct, activeWorkspace.symbol);
  const instrument = getInstrument(state.symbol);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelMessage, setModelMessage] = useState<string | null>(null);

  const result = useMemo(
    () =>
      computeTradeRisk(profile, {
        instrument,
        entry: parseDecimal(state.entry),
        stop: parseDecimal(state.stop),
        target: parseDecimal(state.target),
        riskPct: parseDecimal(state.risk),
        quoteToAccountRate: parseDecimal(state.rate),
      }),
    [profile, instrument, state.entry, state.stop, state.target, state.risk, state.rate],
  );
  const tradeRisk = result.kind === 'ok' ? result.risk.monetaryRisk : null;
  const limits = useMemo(() => (profile.capital ? evaluateLimits(profile, tradeRisk) : null), [profile, tradeRisk]);
  const capacity = remainingRiskCapacity(profile);
  const overall = limits ? worstStatus(limits) : null;

  const useModel = async () => {
    setModelLoading(true);
    setModelMessage(null);
    try {
      const opp = await services.opportunities.getLatest(state.symbol, state.timeframe);
      const plan = planFromOpportunity(opp);
      if (!plan) {
        setModelMessage(`The model reports no opportunity on ${instrument.display} ${state.timeframe}, so there is no plan to load.`);
        return;
      }
      const p = instrument.pricePrecision;
      update({ entry: plan.entry.toFixed(p), stop: plan.stop.toFixed(p), target: plan.target.toFixed(p), origin: 'model' });
      setModelMessage(
        `Loaded the ${opp.direction} plan for ${instrument.display} ${state.timeframe}: midpoints of the model’s zones (entry ${formatPrice(plan.entry, p)}).${opp.provenance === 'demo' ? ' Simulated model output.' : ''}`,
      );
    } catch (e) {
      setModelMessage(`Could not load the model plan: ${userMessage(e)}`);
    } finally {
      setModelLoading(false);
    }
  };

  const assistantHref = `/assistant?symbol=${state.symbol}&tf=${state.timeframe}&q=${encodeURIComponent('Calculate the risk for my capital and stop-loss')}`;

  return (
    <Page>
      <PageHeader
        eyebrow="04 · Risk management"
        title="Capital & risk"
        meta={<SourceTag kind="user" label="Your inputs · saved in this browser" />}
        description="Turn a plan into money: position size from your capital and stop-loss, and every limit checked before you decide. Nothing here places an order."
        actions={
          <Link to={assistantHref} className={buttonClasses({ variant: 'secondary' })}>
            <Bot aria-hidden className="size-4" /> Ask the assistant
          </Link>
        }
      />

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line lg:grid-cols-5">
        <Cell label="Account capital" hint={profile.capital ? profile.currency : 'Set it in your profile'}>
          {profile.capital ? formatMoney(profile.capital, profile.currency) : <span className="text-fg-3">Not set</span>}
        </Cell>
        <Cell label="Max risk per trade" hint={profile.capital ? formatMoney((profile.capital * profile.maxRiskPerTradePct) / 100, profile.currency) : '—'}>
          {formatPct(profile.maxRiskPerTradePct)}
        </Cell>
        <Cell label="Remaining permitted risk" hint={capacity ? `Bound by your ${BINDING_LABEL[capacity.binding]}` : 'Needs capital'} className="col-span-2 lg:col-span-1">
          {capacity ? (
            <span className={capacity.money === 0 ? 'text-danger' : undefined}>
              {formatMoney(capacity.money, profile.currency)} <span className="text-sm text-fg-3">· {formatPct(capacity.pctOfCapital)}</span>
            </span>
          ) : (
            <span className="text-fg-3">—</span>
          )}
        </Cell>
        <Cell label="Open positions" hint="Reported by you">
          {profile.openPositions} <span className="text-sm text-fg-3">/ {profile.maxOpenPositions}</span>
        </Cell>
        <Cell label="This plan" hint={overall ? (tradeRisk !== null ? 'Against all limits' : 'Current usage') : 'Needs capital'}>
          {overall ? (
            <span className={cn('inline-flex items-center gap-1.5 font-sans text-base', STATUS_META[overall].text)}>
              {(() => {
                const Icon = STATUS_META[overall].icon;
                return <Icon aria-hidden className="size-4" />;
              })()}
              {STATUS_META[overall].label}
            </span>
          ) : (
            <span className="text-fg-3">—</span>
          )}
        </Cell>
      </dl>

      {services.source === 'api' && <ServerProfileBanner />}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex min-w-0 flex-col gap-5">
          <section aria-labelledby="planner-title" className="rounded-xl border border-line bg-surface p-4 sm:p-5">
            <h2 id="planner-title" className="mb-4 text-md font-semibold text-fg">
              Plan a trade
            </h2>
            <TradePlanner
              state={state}
              onChange={update}
              onUseModel={useModel}
              modelLoading={modelLoading}
              modelMessage={modelMessage}
              instrument={instrument}
              profile={profile}
              result={result}
            />
            {services.source === 'api' && result.kind === 'ok' && parseDecimal(state.entry) !== null && parseDecimal(state.stop) !== null && (
              <div className="mt-4">
                <ServerCrossCheck
                  instrument={instrument}
                  timeframe={state.timeframe}
                  risk={result.risk}
                  entry={parseDecimal(state.entry) ?? 0}
                  stop={parseDecimal(state.stop) ?? 0}
                  profile={profile}
                  riskPct={parseDecimal(state.risk) ?? profile.maxRiskPerTradePct}
                />
              </div>
            )}
          </section>

          <section aria-labelledby="limits-title" className="rounded-xl border border-line bg-surface p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="limits-title" className="text-md font-semibold text-fg">
                Limit check
              </h2>
              <p className="text-xs text-fg-3">{tradeRisk !== null ? 'Worst case: this trade and every open position hit their stops.' : 'Current usage. Plan a trade to see its effect.'}</p>
            </div>
            {limits ? (
              <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
                {limits.map((l) => (
                  <LimitMeter key={l.id} check={l} currency={profile.currency} showTrade={tradeRisk !== null} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-2">Enter your account capital in the profile to evaluate limits. The platform never assumes a balance.</p>
            )}
          </section>
        </div>

        {/* First step for a new user: on narrow screens the profile comes first until capital is set. */}
        <section aria-labelledby="profile-title" className={cn('rounded-xl border border-line bg-surface px-4 pt-4 sm:px-5 sm:pt-5', !profile.capital && 'order-first xl:order-none')}>
          <h2 id="profile-title" className="mb-4 text-md font-semibold text-fg">
            Your risk profile
          </h2>
          <ProfileForm />
        </section>
      </div>

      {services.source === 'api' && <ServerRiskTemplates />}

      <p className="flex items-start gap-2 text-xs text-fg-3">
        <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        Decision support only. Results depend on the values you enter and assume the stop is filled at its price; gaps and slippage can make real losses larger. This
        platform never places, sizes or closes real orders.
      </p>
    </Page>
  );
}
