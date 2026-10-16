import { ArrowRight, Calculator, Ruler, ShieldCheck } from 'lucide-react';
import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { computeTradeRisk, evaluateLimits } from '@/domain/risk';
import { LimitMeter } from '@/features/risk/LimitMeter';
import { formatMoney, formatPct, formatPrice, formatRiskReward, formatUnits } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { buildShowcase, SHOWCASE_PROFILE, SHOWCASE_SYMBOL } from '../showcase';

const POINTS = [
  { icon: Ruler, title: 'Sized from your stop', text: 'Position size follows from your capital, your risk per trade and the distance to the stop — not from a lot size you guessed.' },
  { icon: ShieldCheck, title: 'Never guesses broker details', text: 'Lots appear only with your broker’s contract size; cross-currency sizing asks for your rate. Missing inputs are named, never filled in.' },
  { icon: Calculator, title: 'Every limit, before you decide', text: 'Per-trade, daily, aggregate and position limits are checked as a worst case, in words and not only colour.' },
];

function Slider({ label, value, min, max, step, onChange, format }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format: (v: number) => string }) {
  const id = useId();
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label htmlFor={id} className="text-sm text-fg-2">
          {label}
        </label>
        <output htmlFor={id} className="num text-lg text-fg">
          {format(value)}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="range mt-2 w-full"
        style={{ '--fill': `${((value - min) / (max - min)) * 100}%` } as React.CSSProperties}
      />
    </div>
  );
}

export function RiskSection() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const [capital, setCapital] = useState(25_000);
  const [riskPct, setRiskPct] = useState(1);
  const profile = useMemo(() => ({ ...SHOWCASE_PROFILE, capital }), [capital]);
  const result = useMemo(() => computeTradeRisk(profile, { instrument: inst, ...s.plan, riskPct, quoteToAccountRate: null }), [profile, inst, s.plan, riskPct]);
  const r = result.kind === 'ok' ? result.risk : null;
  const perTrade = r ? evaluateLimits(profile, r.monetaryRisk).find((l) => l.id === 'per_trade') : undefined;

  return (
    <section id="risk" data-section aria-labelledby="risk-title" className="border-b border-line">
      <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,520px)] lg:items-center">
        <div>
          <p className="eyebrow mb-3">04 · Risk management</p>
          <RevealText as="h2" id="risk-title" className="display text-d3 text-fg sm:text-d2" lines={['A plan is only real', <em key="e">once it is sized.</em>]} />
          <Reveal as="p" delay={150} className="mt-4 max-w-xl text-md text-fg-2">
            The Capital &amp; risk module turns the model’s plan into money against your own limits. It is the one module that works fully today, because it runs on your
            inputs alone.
          </Reveal>
          <ul className="mt-8 flex flex-col gap-5">
            {POINTS.map(({ icon: Icon, title, text }, i) => (
              <Reveal as="li" key={title} index={i} delay={200} className="flex gap-4">
                <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-line-strong text-accent">
                  <Icon aria-hidden className="size-4" />
                </span>
                <span>
                  <span className="block text-md font-medium text-fg">{title}</span>
                  <span className="mt-0.5 block text-sm text-fg-2">{text}</span>
                </span>
              </Reveal>
            ))}
          </ul>
        </div>

        <Reveal variant="scale" className="rounded-2xl border border-line-strong bg-surface p-6 shadow-float">
          <div className="flex items-center justify-between gap-3">
            <p className="text-md font-semibold text-fg">Try it on the demo plan</p>
            <SourceTag kind="user" label="Your input" />
          </div>
          <p className="mt-1 text-xs text-fg-3">
            {inst.display} short · entry {formatPrice(s.plan.entry, inst.pricePrecision)} · stop {formatPrice(s.plan.stop, inst.pricePrecision)} · target{' '}
            {formatPrice(s.plan.target, inst.pricePrecision)} <span className="text-fg-3">(simulated model plan)</span>
          </p>
          <div className="mt-6 flex flex-col gap-5">
            <Slider label="Account capital" value={capital} min={5_000} max={200_000} step={1_000} onChange={setCapital} format={(v) => formatMoney(v, 'USD').replace('.00', '')} />
            <Slider label="Risk per trade" value={riskPct} min={0.25} max={3} step={0.25} onChange={setRiskPct} format={(v) => formatPct(v)} />
          </div>
          {r && (
            <dl aria-live="polite" className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line">
              {[
                ['Position size', formatUnits(r.units, inst.base), ''],
                ['Loss at the stop', formatMoney(r.monetaryRisk, 'USD'), 'text-down'],
                ['Gain at the target', formatMoney(r.potentialReward, 'USD'), 'text-up'],
                ['Reward : risk', formatRiskReward(r.riskReward), ''],
              ].map(([k, v, cls]) => (
                <div key={k} className="bg-surface px-4 py-3">
                  <dt className="text-xs text-fg-3">{k}</dt>
                  <dd className={`num mt-0.5 text-lg ${cls || 'text-fg'}`}>{v}</dd>
                </div>
              ))}
            </dl>
          )}
          {perTrade && riskPct > 1 && (
            <div className="mt-4">
              <LimitMeter check={{ ...perTrade, rule: 'Compared with a 1 % per-trade limit — set your own in the app.' }} currency="USD" />
            </div>
          )}
          <p className="mt-4 text-xs text-fg-3">
            Assumes the stop fills at its price (gaps and slippage can make losses larger). Sizes in ounces; lots need your broker’s contract size. Illustration, not a
            recommendation.
          </p>
          <Link to="/risk" viewTransition className={buttonClasses({ variant: 'secondary', shape: 'pill', className: 'mt-5 w-full' })}>
            Open the full Capital &amp; risk module <ArrowRight aria-hidden className="size-4" />
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
