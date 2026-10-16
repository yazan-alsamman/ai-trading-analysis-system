import { CircleDashed, TriangleAlert } from 'lucide-react';
import { useRef, type CSSProperties } from 'react';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatMoney, formatPct, formatPercent, formatUnits } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useCinematic, useStepProgress } from '@/motion/runtime';
import { ShowcaseChart, type ChartLayer } from '../components/ShowcaseChart';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const STEPS = [
  { title: 'Observed history', text: 'Start with what actually happened: simulated XAU/USD 1-hour candles, the same data the workspace shows in demo mode.' },
  { title: 'The NOW boundary', text: 'Everything left of this line was observed. Everything right of it has not happened yet — and is drawn differently.' },
  { title: 'The model’s projection', text: 'Only the points the model supplied: dashed, violet and after NOW. When the model supplies none, nothing is drawn.' },
  { title: 'Entry, stop and target', text: 'The model’s zones become a plan you can read at a glance, measured from the candle the signal was computed on.' },
  { title: 'Sized to your capital', text: 'The plan becomes money: position size and loss at the stop for your capital and risk per trade.' },
  { title: 'Evidence and uncertainty', text: 'What supports it, what would invalidate it and what is missing — before you decide anything.' },
];

const LAYERS: ChartLayer[][] = [['history'], ['history', 'now'], ['history', 'now', 'projection'], ['history', 'now', 'projection', 'levels']];

export function ChartToPlanSequence() {
  const cinematic = useCinematic();
  const outer = useRef<HTMLDivElement>(null);
  const scrolled = useStepProgress(outer, STEPS.length, cinematic);
  const step = cinematic ? scrolled : STEPS.length - 1;
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const o = s.opportunity;
  const visible = LAYERS[Math.min(step, 3)] ?? LAYERS[3] ?? [];

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

  const evidenceCard = (
    <div className="rounded-xl border border-line-strong bg-surface/95 p-4 shadow-float backdrop-blur">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow">Evidence &amp; uncertainty</p>
        <span className="num text-sm text-forecast">{formatPercent(o.probability)}</span>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5 text-xs">
        {s.invalidation.slice(0, 2).map((n) => (
          <li key={n.key} className="flex gap-2 text-fg-2">
            <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" /> {n.title}
          </li>
        ))}
        <li className="flex gap-2 text-fg-2">
          <CircleDashed aria-hidden className="mt-0.5 size-3.5 shrink-0 text-fg-3" /> {s.missing.length} items missing or unverified (e.g. {s.missing[0]?.title.toLowerCase()})
        </li>
      </ul>
    </div>
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
          <div data-layer data-on={step >= 4} className="absolute -bottom-8 -left-8 w-80">
            {riskCard}
          </div>
          <div data-layer data-on={step >= 5} className="absolute -right-6 -bottom-16 w-[22rem]" style={{ '--layer-delay': '60ms' } as CSSProperties}>
            {evidenceCard}
          </div>
        </>
      ) : (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
          {riskCard}
          {evidenceCard}
        </div>
      )}
    </div>
  );

  const steps = (
    <ol className="flex flex-col gap-1">
      {STEPS.map((st, i) => (
        <li key={st.title} className="relative rounded-xl py-3 pl-14">
          <span
            className={cn(
              'num absolute top-3 left-0 inline-flex size-9 items-center justify-center rounded-full border text-xs transition-colors duration-300',
              i <= step ? 'border-accent text-accent' : 'border-line-strong text-fg-3',
            )}
          >
            {i + 1}
          </span>
          {/* Inactive steps are muted with text tokens (AA contrast), never with opacity. */}
          <p className={cn('text-md font-medium transition-colors duration-300', cinematic && i !== step ? 'text-fg-3' : 'text-fg')}>{st.title}</p>
          <p className={cn('mt-1 text-sm transition-colors duration-300', cinematic && i !== step ? 'text-fg-3' : 'text-fg-2')}>{st.text}</p>
        </li>
      ))}
    </ol>
  );

  return (
    <section id="how-it-works" data-section aria-labelledby="how-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 pt-24 pb-10 sm:px-8">
        <p className="eyebrow mb-3">03 · How it works</p>
        <RevealText as="h2" id="how-title" className="display text-d3 text-fg sm:text-d2" lines={['From a chart', <em key="e">to a research plan.</em>]} />
        <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
          Six steps the workspace takes you through, shown here with the platform’s own simulated demo data. It explains a workflow; it does not predict the market.
        </Reveal>
      </div>
      {cinematic ? (
        <div ref={outer} className="relative h-[360vh]">
          <div className="sticky top-0 flex h-[100svh] items-center">
            <div className="mx-auto grid grid-cols-[minmax(0,1fr)] w-full max-w-[1240px] items-center gap-14 px-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
              {steps}
              {stage}
            </div>
          </div>
        </div>
      ) : (
        <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-10 px-5 pb-24 sm:px-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
          {steps}
          {stage}
        </div>
      )}
    </section>
  );
}
