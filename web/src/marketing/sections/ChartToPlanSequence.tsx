import { CircleCheck, CircleDashed, FileText, TriangleAlert } from 'lucide-react';
import { useRef, type CSSProperties } from 'react';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatMoney, formatPct, formatPercent, formatPrice, formatRiskReward, formatUnits } from '@/lib/format';
import { CinematicVideo } from '@/motion/CinematicVideo';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useCinematic, useStepProgress } from '@/motion/runtime';
import { ShowcaseChart, type ChartLayer } from '../components/ShowcaseChart';
import { FOOTAGE } from '../media';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const STEPS = [
  { title: 'Observed history', text: 'Start with what actually happened: simulated XAU/USD 1-hour candles, the same data the workspace shows in demo mode.' },
  { title: 'The NOW boundary', text: 'Everything left of this line was observed. Everything right of it has not happened yet — and is drawn differently.' },
  { title: 'The model’s projection', text: 'Only the points the model supplied: dashed, violet and after NOW. When the model supplies none, nothing is drawn.' },
  { title: 'Entry, stop and target', text: 'The model’s zones become levels you can read at a glance, measured from the candle the signal was computed on.' },
  { title: 'Evidence and your checks', text: 'What pushed the model towards this view, and whether it passes the rules in your own signal profile.' },
  { title: 'Sized to your capital', text: 'The levels become money: position size and loss at the stop for your capital and risk per trade.' },
  { title: 'A structured research plan', text: 'Thesis, levels, size, checks, what would invalidate it and what is missing — one page, before you decide anything.' },
];

const LAYERS: ChartLayer[][] = [['history'], ['history', 'now'], ['history', 'now', 'projection'], ['history', 'now', 'projection', 'levels']];

/**
 * Scene C — from a chart to a research plan. Pinned on wide screens: each
 * step adds one layer to the chart or one card, ending in the structured plan.
 * Elsewhere every layer and card is shown at once.
 */
export function ChartToPlanSequence() {
  const cinematic = useCinematic();
  const outer = useRef<HTMLDivElement>(null);
  const scrolled = useStepProgress(outer, STEPS.length, cinematic);
  const step = cinematic ? scrolled : STEPS.length - 1;
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const o = s.opportunity;
  const visible = LAYERS[Math.min(step, 3)] ?? LAYERS[3] ?? [];
  const top = [...o.factors].sort((a, b) => b.contribution - a.contribution).slice(0, 3);
  const passed = s.evaluation.checks.filter((c) => c.status === 'pass').length;
  const price = (v: number) => formatPrice(v, inst.pricePrecision);

  const evidenceCard = (
    <div className="rounded-xl border border-line-strong bg-surface/95 p-4 shadow-float backdrop-blur">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow">Evidence &amp; checks</p>
        <span className="num text-sm text-forecast">{formatPercent(o.probability)}</span>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5 text-xs">
        {top.map((f) => (
          <li key={f.id} className="flex justify-between gap-3 text-fg-2">
            <span className="truncate">{f.label}</span>
            <span className="num text-fg-3">
              {f.contribution >= 0 ? '+' : '−'}
              {Math.abs(f.contribution).toFixed(2)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 flex items-center gap-2 border-t border-line pt-2.5 text-xs text-fg-2">
        <CircleCheck aria-hidden className="size-3.5 text-accent" />
        <span>
          <span className="num">{passed}</span> of <span className="num">{s.evaluation.checks.length}</span> profile checks pass
        </span>
      </p>
    </div>
  );

  const riskCard = (
    <div className="rounded-xl border border-line-strong bg-surface/95 p-4 shadow-float backdrop-blur">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow">Risk plan</p>
        <SourceTag kind="user" label="Example: $25,000 · 1 %" />
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        <div>
          <dt className="text-xs text-fg-3">Position</dt>
          <dd className="num text-md text-fg">{formatUnits(s.risk.units, inst.base)}</dd>
        </div>
        <div>
          <dt className="text-xs text-fg-3">Loss at stop</dt>
          <dd className="num text-md text-down">{formatMoney(s.risk.monetaryRisk, 'USD')}</dd>
        </div>
        <div>
          <dt className="text-xs text-fg-3">Of capital</dt>
          <dd className="num text-md text-fg">{formatPct(s.risk.riskPctOfCapital)}</dd>
        </div>
      </dl>
    </div>
  );

  const planCard = (
    <article aria-label="Structured research plan (simulated example)" className="rounded-2xl border border-accent/50 bg-surface p-5 shadow-float">
      <div className="flex items-center gap-2">
        <FileText aria-hidden className="size-4 text-accent" />
        <p className="text-sm font-semibold text-fg">Research plan</p>
        <span className="text-sm text-fg-3">
          · {inst.display} {SHOWCASE_TIMEFRAME}
        </span>
        <DirectionBadge direction={o.direction} className="ml-auto" />
      </div>
      <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
        <dt className="text-fg-3">Thesis</dt>
        <dd className="text-fg">
          {formatPercent(o.probability)} that the target is reached before the stop; strongest evidence “{top[0]?.label ?? '—'}”.
        </dd>
        <dt className="text-fg-3">Levels</dt>
        <dd className="num text-fg">
          Entry {price(s.plan.entry)} · Stop {price(s.plan.stop)} · Target {price(s.plan.target)} · {formatRiskReward(s.risk.riskReward)}
        </dd>
        <dt className="text-fg-3">Size</dt>
        <dd className="num text-fg">
          {formatUnits(s.risk.units, inst.base)} · <span className="text-down">{formatMoney(s.risk.monetaryRisk, 'USD')}</span> at the stop ({formatPct(s.risk.riskPctOfCapital)})
        </dd>
        <dt className="text-fg-3">Checks</dt>
        <dd className="text-fg">
          {passed} of {s.evaluation.checks.length} pass — {s.evaluation.matches ? 'matches your profile' : 'outside your profile'}
        </dd>
        <dt className="text-fg-3">Invalidated if</dt>
        <dd className="flex gap-1.5 text-fg">
          <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" />
          {s.invalidation[0]?.title ?? 'No invalidation conditions supplied'}
        </dd>
        <dt className="text-fg-3">Missing</dt>
        <dd className="flex gap-1.5 text-fg-2">
          <CircleDashed aria-hidden className="mt-0.5 size-3.5 shrink-0 text-fg-3" />
          {s.missing.length} items missing or unverified (e.g. {s.missing[0]?.title.toLowerCase() ?? '—'})
        </dd>
      </dl>
      <p className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3 text-xs text-fg-3">
        Research, not advice: you decide, and you place any trade yourself.
        <SourceTag kind="demo" />
      </p>
    </article>
  );

  const stage = (
    <div className="relative">
      <figure className="overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-float">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <span className="text-sm font-semibold text-fg">{inst.display}</span>
          <span className="text-sm text-fg-3">· {SHOWCASE_TIMEFRAME}</span>
          <span className="ml-auto text-xs text-fg-3" aria-live="polite">
            {cinematic ? `Step ${step + 1} of ${STEPS.length}` : 'All steps'}
          </span>
          <SourceTag kind="demo" />
        </div>
        <div className="px-2 pt-3 pb-2">
          <ShowcaseChart
            candles={s.candles}
            opportunity={o}
            timeframe={SHOWCASE_TIMEFRAME}
            precision={inst.pricePrecision}
            variant="candles"
            mode="steps"
            visible={visible}
            label={`Simulated ${inst.display} candles; ${visible.join(', ')} shown.`}
          />
        </div>
      </figure>
      {cinematic ? (
        <>
          <div data-layer data-on={step === 4 || step === 5} className="absolute -right-6 -bottom-12 w-[21rem]">
            {evidenceCard}
          </div>
          <div data-layer data-on={step === 5} className="absolute -bottom-8 -left-8 w-80" style={{ '--layer-delay': '60ms' } as CSSProperties}>
            {riskCard}
          </div>
          <div data-layer data-on={step >= 6} className="absolute inset-x-10 top-10" style={{ '--layer-delay': '120ms' } as CSSProperties}>
            {planCard}
          </div>
        </>
      ) : (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
          {evidenceCard}
          {riskCard}
          <div className="sm:col-span-2">{planCard}</div>
        </div>
      )}
    </div>
  );

  const steps = (
    <ol className="flex flex-col gap-0.5">
      {STEPS.map((st, i) => (
        <li key={st.title} className="relative rounded-xl py-2.5 pl-14">
          <span
            className={cn(
              'num absolute top-2.5 left-0 inline-flex size-9 items-center justify-center rounded-full border text-xs transition-colors duration-300',
              i <= step ? 'border-accent text-accent' : 'border-line-strong text-fg-3',
            )}
          >
            {i + 1}
          </span>
          {/* Inactive steps are muted with text tokens (AA contrast), never with opacity. */}
          <p className={cn('text-md font-medium transition-colors duration-300', cinematic && i !== step ? 'text-fg-3' : 'text-fg')}>{st.title}</p>
          {/* The active step's explanation opens; the rest stay one line each. */}
          <div className="accordion-panel" data-open={!cinematic || i === step}>
            <div>
              <p className="mt-1 text-sm text-fg-2">{st.text}</p>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );

  return (
    <section id="how-it-works" data-section aria-labelledby="how-title" className="border-b border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] items-end gap-8 px-5 pt-24 pb-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
        <div>
          <p className="eyebrow mb-3">04 · How it works</p>
          <RevealText as="h2" id="how-title" className="display text-d3 text-fg sm:text-d2" lines={['From a chart', <em key="e">to a research plan.</em>]} />
          <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
            Seven steps the workspace takes you through, shown here with the platform’s own simulated demo data. It explains a workflow; it does not predict the market.
          </Reveal>
        </div>
        <Reveal variant="scale" delay={120} className="relative hidden aspect-[16/9] overflow-hidden rounded-2xl border border-line md:block">
          <CinematicVideo {...FOOTAGE.workflow} />
          <div className="footage-veil absolute inset-0" aria-hidden />
        </Reveal>
      </div>
      {cinematic ? (
        <div ref={outer} className="relative h-[400vh]">
          <div className="sticky top-0 flex h-[100svh] items-center">
            <div className="mx-auto grid grid-cols-[minmax(0,1fr)] w-full max-w-[1240px] items-center gap-14 px-8 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
              {steps}
              {stage}
            </div>
          </div>
        </div>
      ) : (
        <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-10 px-5 pb-24 sm:px-8 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          {steps}
          {stage}
        </div>
      )}
    </section>
  );
}
