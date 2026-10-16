import { ArrowDownRight, ArrowUpRight, ChevronRight, CircleDashed, OctagonAlert, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select } from '@/components/ui/Form';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { SourceTag } from '@/components/ui/SourceTag';
import { INSTRUMENTS, type Instrument, type InstrumentSymbol } from '@/domain/instruments';
import { TIMEFRAMES, type Timeframe } from '@/domain/market';
import type { RiskProfile, TradeRisk, TradeRiskResult } from '@/domain/risk';
import { cn } from '@/lib/cn';
import { formatMoney, formatNumber, formatPct, formatPips, formatPrice, formatRiskReward, formatUnits } from '@/lib/format';
import { numberError, parseDecimal } from './parse';

export interface PlannerState {
  symbol: InstrumentSymbol;
  timeframe: Timeframe;
  entry: string;
  stop: string;
  target: string;
  risk: string;
  rate: string;
  /** 'model' while the levels are unchanged from the model's plan. */
  origin: 'model' | 'user';
}

interface Props {
  state: PlannerState;
  onChange: (patch: Partial<PlannerState>) => void;
  onUseModel: () => void;
  modelLoading: boolean;
  modelMessage: string | null;
  instrument: Instrument;
  profile: RiskProfile;
  result: TradeRiskResult;
}

function Hero({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: 'up' | 'down' }) {
  return (
    <div className="min-w-0 bg-surface px-4 py-3.5">
      <dt className="text-xs text-fg-3">{label}</dt>
      <dd className={cn('num mt-1 truncate text-xl leading-tight', tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-fg')}>{value}</dd>
      {sub && <dd className="mt-1 truncate text-xs text-fg-3">{sub}</dd>}
    </div>
  );
}

/** Stop ← entry → target, to scale, with the money at each end. */
function RiskLadder({ risk, instrument, entry, stop, target, currency }: { risk: TradeRisk; instrument: Instrument; entry: number; stop: number; target: number | null; currency: string }) {
  const p = instrument.pricePrecision;
  const total = risk.stopDistance + (risk.targetDistance ?? risk.stopDistance);
  const riskShare = (risk.stopDistance / total) * 100;
  return (
    <figure className="flex flex-col gap-2" aria-label="Trade plan drawn to scale">
      <div className="flex h-2.5 overflow-hidden rounded-full">
        <span className="bg-down/55" style={{ width: `${riskShare}%` }} />
        <span className="w-0.5 bg-fg" />
        <span className={target !== null ? 'flex-1 bg-up/55' : 'flex-1 bg-hover'} />
      </div>
      <figcaption className="num grid grid-cols-3 text-xs">
        <span>
          <span className="block text-fg-3">Stop</span>
          <span className="text-down">{formatPrice(stop, p)}</span>
          <span className="block text-fg-2">{formatMoney(-risk.monetaryRisk, currency)}</span>
        </span>
        <span className="text-center">
          <span className="block text-fg-3">Entry · {risk.direction === 'long' ? 'long' : 'short'}</span>
          <span className="text-fg">{formatPrice(entry, p)}</span>
        </span>
        <span className="text-right">
          <span className="block text-fg-3">Target</span>
          {target !== null ? (
            <>
              <span className="text-up">{formatPrice(target, p)}</span>
              <span className="block text-fg-2">{formatMoney(risk.potentialReward, currency, { signed: true })}</span>
            </>
          ) : (
            <span className="text-fg-3">not set</span>
          )}
        </span>
      </figcaption>
    </figure>
  );
}

export function TradePlanner({ state, onChange, onUseModel, modelLoading, modelMessage, instrument, profile, result }: Props) {
  const entry = parseDecimal(state.entry);
  const stop = parseDecimal(state.stop);
  const target = parseDecimal(state.target);
  const riskPct = parseDecimal(state.risk);
  const rate = parseDecimal(state.rate);
  const fieldIssue = (f: string) => (result.kind !== 'ok' ? result.issues.find((i) => i.field === f)?.message : undefined);
  const needsRate = instrument.quote !== profile.currency && instrument.base !== profile.currency;
  const p = instrument.pricePrecision;
  const step = String(10 ** -p);

  const priceField = (key: 'entry' | 'stop' | 'target', label: string, value: number | null, optional = false) => {
    const err = numberError(value, { label: `the ${label.toLowerCase()}` }) ?? (state[key] ? fieldIssue(key) : undefined);
    return (
      <Field label={label} optional={optional} error={err}>
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            inputMode="decimal"
            autoComplete="off"
            step={step}
            placeholder={`Price (${p} dp)`}
            aria-describedby={describedBy}
            invalid={invalid}
            value={state[key]}
            onChange={(e) => onChange({ [key]: e.target.value, origin: 'user' })}
            className="num"
          />
        )}
      </Field>
    );
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Instrument" className="w-40">
          {({ id }) => (
            <Select id={id} value={state.symbol} onChange={(e) => onChange({ symbol: e.target.value as InstrumentSymbol, entry: '', stop: '', target: '', rate: '', origin: 'user' })}>
              {INSTRUMENTS.map((i) => (
                <option key={i.symbol} value={i.symbol}>
                  {i.display}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-fg">Model timeframe</span>
          <SegmentedControl
            label="Timeframe for the model plan"
            value={state.timeframe}
            options={TIMEFRAMES.map((t) => ({ value: t.id, label: t.label }))}
            onChange={(timeframe) => onChange({ timeframe })}
            size="md"
          />
        </div>
        <Button icon={Sparkles} onClick={onUseModel} loading={modelLoading} className="sm:ml-auto">
          Use model plan
        </Button>
      </div>
      {modelMessage && <p className="-mt-2 text-xs text-fg-3">{modelMessage}</p>}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {priceField('entry', 'Entry', entry)}
        {priceField('stop', 'Stop-loss', stop)}
        {priceField('target', 'Target', target, true)}
        <Field label="Risk on this trade" error={numberError(riskPct, { label: 'the risk', max: 100 }) ?? (state.risk ? fieldIssue('riskPct') : undefined)} hint={`Your maximum: ${formatPct(profile.maxRiskPerTradePct)}`}>
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <Input id={id} inputMode="decimal" aria-describedby={describedBy} invalid={invalid} value={state.risk} onChange={(e) => onChange({ risk: e.target.value })} className="num pr-8" />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-fg-3">%</span>
            </div>
          )}
        </Field>
      </div>

      {needsRate && (
        <Field
          label={`Conversion rate: 1 ${instrument.quote} = ? ${profile.currency}`}
          hint={`Needed because ${instrument.display} is quoted in ${instrument.quote} and your account is in ${profile.currency}. Use your broker’s current rate — the platform will not guess it.`}
          error={numberError(rate, { label: 'the rate' })}
          className="max-w-md"
        >
          {({ id, describedBy, invalid }) => (
            <Input id={id} inputMode="decimal" aria-describedby={describedBy} invalid={invalid} value={state.rate} onChange={(e) => onChange({ rate: e.target.value })} className="num" />
          )}
        </Field>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
        Levels: {state.origin === 'model' ? <SourceTag kind="model" label="Model plan (zone midpoints)" /> : <SourceTag kind="user" />}
        <span>· Risk %, capital and limits: <SourceTag kind="user" /></span>
      </div>

      <section aria-label="Result" aria-live="polite" className="rounded-xl border border-line bg-inset">
        {result.kind === 'incomplete' && (
          <div className="flex items-start gap-3 p-4">
            <CircleDashed aria-hidden className="mt-0.5 size-5 shrink-0 text-fg-3" />
            <div>
              <p className="text-sm font-medium text-fg">Nothing is calculated until every required input is known</p>
              <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-sm text-fg-2">
                {result.issues.map((i) => (
                  <li key={i.field}>{i.message}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {result.kind === 'invalid' && (
          <div role="alert" className="flex items-start gap-3 p-4">
            <OctagonAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
            <div>
              <p className="text-sm font-medium text-fg">This plan is not consistent</p>
              <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-sm text-fg-2">
                {result.issues.map((i) => (
                  <li key={i.field + i.message}>{i.message}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {result.kind === 'ok' && entry !== null && stop !== null && (
          <>
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-t-xl bg-line lg:grid-cols-4">
              <Hero
                label="Position size"
                value={formatUnits(result.risk.units, instrument.base)}
                sub={
                  result.risk.lots
                    ? `${formatNumber(result.risk.lots.rounded ?? result.risk.lots.exact, result.risk.lots.rounded !== null ? 2 : 4)} lots`
                    : 'Lots: add contract size'
                }
              />
              <Hero label="Money at risk" value={formatMoney(result.risk.monetaryRisk, profile.currency)} sub={`${formatPct(result.risk.riskPctOfCapital)} of capital`} tone="down" />
              <Hero
                label="Potential reward"
                value={result.risk.potentialReward !== null ? formatMoney(result.risk.potentialReward, profile.currency) : '—'}
                sub={result.risk.rewardPctOfCapital !== null ? `${formatPct(result.risk.rewardPctOfCapital)} of capital` : 'Enter a target'}
                tone={result.risk.potentialReward !== null ? 'up' : undefined}
              />
              <Hero
                label="Reward : risk"
                value={formatRiskReward(result.risk.riskReward)}
                sub={
                  <span className="inline-flex items-center gap-1">
                    {result.risk.direction === 'long' ? <ArrowUpRight aria-hidden className="size-3.5" /> : <ArrowDownRight aria-hidden className="size-3.5" />}
                    {result.risk.direction === 'long' ? 'Long' : 'Short'} · stop {instrument.kind === 'fx' ? formatPips(result.risk.stopDistance, instrument.pipSize) : formatPrice(result.risk.stopDistance, p)} away
                  </span>
                }
              />
            </dl>
            <div className="flex flex-col gap-4 p-4">
              <RiskLadder risk={result.risk} instrument={instrument} entry={entry} stop={stop} target={target} currency={profile.currency} />
              <details className="group">
                <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-fg-2 hover:text-fg">
                  <ChevronRight aria-hidden className="size-3.5 transition-transform group-open:rotate-90" />
                  How this is calculated
                </summary>
                <ol className="mt-2 flex list-decimal flex-col gap-1 pl-5 text-xs text-fg-2">
                  <li>
                    Risk budget = capital × risk % = <span className="num text-fg">{formatMoney(result.risk.riskBudget, profile.currency)}</span>
                  </li>
                  <li>
                    Stop distance = |entry − stop| = <span className="num text-fg">{formatPrice(result.risk.stopDistance, p)}</span> {instrument.quote} per {instrument.kind === 'metal' ? 'ounce' : instrument.base}
                  </li>
                  <li>
                    Size = risk budget ÷ (stop distance × conversion) = <span className="num text-fg">{formatUnits(result.risk.units, instrument.base)}</span>
                    {result.risk.lots?.rounded !== null && result.risk.lots ? ' (after rounding lots down)' : ''}
                  </li>
                  <li>
                    Notional value at entry ≈ <span className="num text-fg">{formatMoney(result.risk.notional, profile.currency)}</span>. Margin is not shown: it depends on your broker’s leverage.
                  </li>
                  {result.notes.map((n) => (
                    <li key={n} className="list-none text-fg-3">
                      {n}
                    </li>
                  ))}
                </ol>
              </details>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
