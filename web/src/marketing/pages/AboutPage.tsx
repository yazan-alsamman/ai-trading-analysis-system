import { ArrowRight, Ban, Bot, Calculator, CandlestickChart, Check, FileText, Gauge, Newspaper, Radar, Scale, UserRound } from 'lucide-react';
import { useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { Link } from 'react-router';
import { Badge } from '@/components/ui/Badge';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { DirectionBadge } from '@/components/ui/Market';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { SOURCE_DEFINITIONS, SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { FEATURES, type FeatureStatus } from '@/domain/membership';
import { computeTradeRisk } from '@/domain/risk';
import { buildDemoNews } from '@/fixtures/community';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';
import { cn } from '@/lib/cn';
import { formatMoney, formatPercent, formatProbabilityBand, formatUnits } from '@/lib/format';
import { CinematicVideo } from '@/motion/CinematicVideo';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useInView, useSingleColumn } from '@/motion/runtime';
import { StatusBadge } from '../membership/PlanComponents';
import { FOOTAGE } from '../media';
import { ExposureGauge } from '../sections/RiskSection';
import { buildShowcase, SHOWCASE_ANCHOR, SHOWCASE_PROFILE, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const at = (ms: number) => ({ '--at': `${ms}ms` }) as CSSProperties;
const statusOf = (id: string): FeatureStatus => FEATURES.find((f) => f.id === id)?.status ?? 'planned';

/** Plays its children's timed animations once the block is in view. */
function InViewPlay({ children, className, as: Tag = 'div' }: { children: ReactNode; className?: string; as?: 'div' | 'section' | 'ul' }) {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref);
  return (
    <Tag ref={ref as never} data-play={seen} className={className}>
      {children}
    </Tag>
  );
}

function SectionHead({ eyebrow, id, lines, children, center = false }: { eyebrow: string; id: string; lines: ReactNode[]; children?: ReactNode; center?: boolean }) {
  return (
    <div className={cn('max-w-3xl', center && 'mx-auto text-center')}>
      <p className="eyebrow mb-3">{eyebrow}</p>
      <RevealText as="h2" id={id} className="display text-d3 text-fg sm:text-d2" lines={lines} />
      {children && (
        <Reveal as="p" delay={150} className={cn('mt-4 max-w-2xl text-md text-fg-2', center && 'mx-auto')}>
          {children}
        </Reveal>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ 1. Hero */

function AboutHero() {
  const s = buildShowcase();
  const column = useSingleColumn();
  const closes = s.candles.map((c) => c.close);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  const pts = closes.map((v, i) => [(i / (closes.length - 1)) * 600, 210 - ((v - lo) / (hi - lo || 1)) * 120] as const);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  // Three moments on the line become three research notes.
  const marks = [Math.round(closes.length * 0.28), Math.round(closes.length * 0.6), closes.length - 1].map((i) => pts[i] ?? [0, 0]);
  const notes = ['Observed price · simulated', 'Evidence attached', 'Risk sized to a limit'];

  return (
    <section aria-labelledby="about-title" className="atmosphere relative isolate overflow-hidden border-b border-line pt-28 pb-16 lg:min-h-[92svh] lg:pt-36">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] items-center gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)]">
        <div className="flex flex-col gap-7">
          <p className="eyebrow m-in flex items-center gap-2" style={at(0)}>
            <span aria-hidden className="size-1.5 rounded-full bg-accent" /> About AI Trading Assistance
          </p>
          <RevealText
            as="h1"
            id="about-title"
            trigger="mount"
            delay={80}
            className="display text-[2.75rem] leading-[0.98] text-fg sm:text-d1"
            lines={['A clearer way', <em key="e">to read the markets.</em>]}
          />
          <p className="m-in-blur max-w-xl text-md text-fg-2 sm:text-[1.0625rem] sm:leading-7" style={at(450)}>
            We are building a research platform for gold and FX that turns charts, a model’s assessment and your own risk limits into one structured, sourced
            workflow. It helps you reason before you trade. It never trades for you.
          </p>
          <div className="m-in flex flex-wrap items-center gap-3" style={at(800)}>
            <Link to="/#platform" viewTransition className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill' })}>
              Explore the platform <ArrowRight aria-hidden className="size-4" />
            </Link>
            <Link to="/#methodology" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
              Read the methodology
            </Link>
            <Link to="/membership" viewTransition className="px-2 text-sm text-fg-2 underline-offset-4 hover:text-fg hover:underline">
              or view membership →
            </Link>
          </div>
        </div>

        {/* Footage with the research trace laid over it */}
        <figure className="m-stage relative overflow-hidden rounded-3xl border border-line-strong bg-canvas shadow-float" style={at(300)}>
          <div className="relative aspect-[4/3]">
            <CinematicVideo {...FOOTAGE.closing} priority phone={column ? 'poster' : 'video'} className="absolute inset-0" />
            <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-canvas via-canvas/40 to-transparent" />
            <svg viewBox="0 0 600 240" aria-hidden className="absolute inset-x-0 bottom-0 h-auto w-full">
              <path d={line} fill="none" pathLength={1} className="m-draw stroke-accent" strokeWidth="2" strokeLinejoin="round" style={{ '--at': '900ms', '--dur': '1600ms', '--len': 1 } as CSSProperties} />
              {marks.map(([x, y], i) => (
                <g key={i}>
                  <line x1={x} x2={x} y1={y} y2={40 + i * 8} className="m-fade stroke-fg-3" strokeDasharray="2 3" style={at(1700 + i * 260)} />
                  <circle cx={x} cy={y} r="4.5" className="m-pop fill-canvas stroke-accent" strokeWidth="2" style={at(1500 + i * 260)} />
                </g>
              ))}
            </svg>
            <ul aria-label="From market data to structured analysis" className="absolute inset-x-3 top-3 flex flex-wrap gap-2 sm:inset-x-4 sm:top-4">
              {notes.map((n, i) => (
                <li key={n} className="m-in rounded-full border border-line-strong bg-surface px-3 py-1 text-xs text-fg" style={at(1800 + i * 260)}>
                  {n}
                </li>
              ))}
            </ul>
          </div>
          <figcaption className="flex items-center gap-2 border-t border-line px-4 py-2.5 text-xs text-fg-3">
            <SourceTag kind="demo" /> Line: simulated XAU/USD closes. Footage: licensed stock, illustrative.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- 2. Problem */

const FRAGMENTS = [
  { text: 'Price broke the morning high', kind: 'Market context' },
  { text: 'RSI at 74 — overbought?', kind: 'Technicals' },
  { text: 'US data release on Friday', kind: 'Events' },
  { text: '“Short gold now” in a chat', kind: 'Opinion' },
  { text: '1h says short, 4h says long', kind: 'Timeframes' },
  { text: 'How much should I risk?', kind: 'Risk' },
];
const ORDERED = ['Context — sessions and scheduled events', 'Chart — observed history and the NOW boundary', 'Model output — direction, probability, zones', 'Evidence — factors, checks, invalidation', 'Risk — size and loss at the stop for your limits', 'Decision — yours, with what is still missing'];

function ProblemScene() {
  return (
    <section id="about-problem" data-section aria-labelledby="about-problem-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <SectionHead eyebrow="01 · The problem" id="about-problem-title" lines={['Markets don’t arrive', <em key="e">organised.</em>]}>
          Prices, indicators, scheduled events and other people’s opinions arrive at once, and they rarely agree. The hard part of trading research is not finding
          information. It is putting each piece where it belongs and seeing what is still missing.
        </SectionHead>
        <InViewPlay className="mt-14 grid grid-cols-[minmax(0,1fr)] items-center gap-6 lg:grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)]">
          <ul aria-label="Fragments of information" className="flex flex-col gap-2.5">
            {FRAGMENTS.map((f, i) => (
              <li
                key={f.text}
                className="m-in flex items-center justify-between gap-3 rounded-xl border border-dashed border-line-strong bg-canvas px-4 py-2.5 text-sm text-fg-2"
                style={{ ...at(i * 90), marginLeft: `${[0, 18, 6, 26, 10, 2][i]}px` }}
              >
                {f.text}
                <span className="text-xs text-fg-3">{f.kind}</span>
              </li>
            ))}
          </ul>
          <svg aria-hidden viewBox="0 0 120 300" preserveAspectRatio="none" className="hidden h-[300px] w-full lg:block">
            {FRAGMENTS.map((_, i) => (
              <path
                key={i}
                d={`M0 ${25 + i * 50} C60 ${25 + i * 50}, 60 150, 120 150`}
                fill="none"
                pathLength={1}
                vectorEffect="non-scaling-stroke"
                className="m-draw stroke-accent"
                strokeOpacity="0.5"
                strokeWidth="1"
                style={{ '--at': `${600 + i * 80}ms`, '--dur': '700ms', '--len': 1 } as CSSProperties}
              />
            ))}
          </svg>
          <div className="m-stage rounded-2xl border border-accent/40 bg-surface p-5 shadow-float" style={at(1100)}>
            <p className="flex items-center gap-2 text-sm font-semibold text-fg">
              <FileText aria-hidden className="size-4 text-accent" /> One research view
            </p>
            <ol className="mt-4 flex flex-col gap-2">
              {ORDERED.map((o, i) => (
                <li key={o} className="m-in flex gap-3 text-sm text-fg-2" style={at(1300 + i * 110)}>
                  <span className="num inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-accent/60 text-xs text-accent">{i + 1}</span>
                  {o}
                </li>
              ))}
            </ol>
          </div>
        </InViewPlay>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------- 3. Capabilities */

function MiniChart() {
  const s = buildShowcase();
  const c = s.candles.slice(-28);
  const lo = Math.min(...c.map((k) => k.low));
  const hi = Math.max(...c.map((k) => k.high));
  const y = (v: number) => 8 + (1 - (v - lo) / (hi - lo || 1)) * 104;
  return (
    <svg viewBox="0 0 300 120" aria-hidden className="h-full w-full">
      {c.map((k, i) => {
        const x = 8 + i * 10;
        const up = k.close >= k.open;
        return (
          <g key={k.time} className={cn('m-fade', up ? 'fill-up stroke-up' : 'fill-down stroke-down')} style={at(i * 25)}>
            <line x1={x} x2={x} y1={y(k.high)} y2={y(k.low)} strokeWidth="1" />
            <rect x={x - 3} y={Math.min(y(k.open), y(k.close))} width="6" height={Math.max(1.5, Math.abs(y(k.open) - y(k.close)))} rx="1" strokeWidth="0" />
          </g>
        );
      })}
      <line x1="286" x2="286" y1="4" y2="116" className="m-fade stroke-fg-3" strokeDasharray="3 3" style={at(800)} />
    </svg>
  );
}

function MiniSignal() {
  const o = buildShowcase().opportunity;
  return (
    <div className="flex h-full flex-col justify-center gap-2 text-xs">
      <div className="m-in flex items-center gap-2" style={at(0)}>
        <span className="font-medium text-fg">{getInstrument(SHOWCASE_SYMBOL).display}</span>
        <span className="num text-fg-3">{SHOWCASE_TIMEFRAME}</span>
        <DirectionBadge direction={o.direction} />
        <span className="num ml-auto text-sm text-forecast">{formatPercent(o.probability)}</span>
      </div>
      {[
        ['Target zone', 'bg-up/70', 0.86],
        ['Entry zone', 'bg-accent/80', 0.62],
        ['Stop zone', 'bg-down/70', 0.42],
      ].map(([l, cls, w], i) => (
        <div key={l as string} className="flex items-center gap-2">
          <span className="w-20 text-fg-3">{l}</span>
          <span className="h-1.5 flex-1 rounded-full bg-line">
            <span className={cn('m-grow-x block h-full rounded-full', cls as string)} style={{ width: `${(w as number) * 100}%`, ...at(200 + i * 140) }} />
          </span>
        </div>
      ))}
    </div>
  );
}

function MiniRisk() {
  const r = buildShowcase().risk;
  return (
    <dl className="grid h-full grid-cols-2 content-center gap-x-4 gap-y-2 text-xs">
      {[
        ['Capital', formatMoney(SHOWCASE_PROFILE.capital, 'USD').replace('.00', ''), 'text-fg'],
        ['Risk per trade', '1 %', 'text-fg'],
        ['Position', formatUnits(r.units, getInstrument(SHOWCASE_SYMBOL).base), 'text-fg'],
        ['Loss at the stop', formatMoney(r.monetaryRisk, 'USD'), 'text-down'],
      ].map(([k, v, cls], i) => (
        <div key={k} className="m-in" style={at(i * 110)}>
          <dt className="text-fg-3">{k}</dt>
          <dd className={cn('num text-md', cls)}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function MiniNews() {
  const news = buildDemoNews(SHOWCASE_ANCHOR * 1000).slice(0, 2);
  return (
    <ul className="flex h-full flex-col justify-center gap-2.5 text-xs">
      {news.map((n, i) => (
        <li key={n.id} className="m-in" style={at(i * 140)}>
          <Badge tone={n.impact === 'high' ? 'warning' : 'neutral'}>{n.impact} impact</Badge>
          <p className="mt-1 line-clamp-2 text-fg-2">{n.title}</p>
        </li>
      ))}
    </ul>
  );
}

function MiniAssistant() {
  return (
    <div className="flex h-full flex-col justify-center gap-2 text-xs">
      <p className="m-in ml-auto rounded-xl rounded-tr-sm bg-selected px-3 py-1.5 text-fg" style={at(0)}>
        What would invalidate this?
      </p>
      <div className="m-in flex gap-2" style={at(300)}>
        <span aria-hidden className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-forecast-soft text-forecast">
          <Bot className="size-3" />
        </span>
        <p className="rounded-xl border border-forecast/30 px-3 py-1.5 text-fg-2">Price trading above the stop-loss zone; the 20-candle horizon running out; a newer analysis…</p>
      </div>
    </div>
  );
}

function MiniCalibration() {
  const bins = buildShowcase().stats.calibration.filter((b) => b.count > 0);
  const pts = bins.map((b) => `${(10 + b.meanPredicted * 280).toFixed(1)} ${(110 - b.observedRate * 100).toFixed(1)}`);
  return (
    <svg viewBox="0 0 300 120" aria-hidden className="h-full w-full">
      <path d="M10 110 L290 10" className="stroke-fg-3" strokeDasharray="3 4" strokeWidth="1" fill="none" />
      <path d={`M${pts.join(' L')}`} fill="none" pathLength={1} className="m-draw stroke-forecast" strokeWidth="1.5" style={{ '--at': '100ms', '--dur': '1100ms', '--len': 1 } as CSSProperties} />
      {bins.map((b, i) => (
        <circle key={b.from} cx={10 + b.meanPredicted * 280} cy={110 - b.observedRate * 100} r="3.5" className="m-pop fill-forecast" style={at(200 + i * 120)} />
      ))}
    </svg>
  );
}

const CAPABILITIES: { icon: typeof CandlestickChart; title: string; text: string; status: FeatureStatus; visual: () => ReactNode }[] = [
  {
    icon: CandlestickChart,
    title: 'Charts that separate observed from projected',
    text: 'Candles on 15m, 1h and 4h with indicators. A NOW boundary divides what happened from anything the model projects.',
    status: statusOf('workspace'),
    visual: MiniChart,
  },
  {
    icon: Radar,
    title: 'Model signals with entry, stop and target zones',
    text: 'Direction, a probability that the target comes before the stop, and zones measured from the candle the signal was computed on.',
    status: statusOf('ai_analysis'),
    visual: MiniSignal,
  },
  {
    icon: Calculator,
    title: 'Position sizing from your own limits',
    text: 'Size, money at risk and limit checks from your capital and stop distance. It never guesses broker contract sizes or exchange rates.',
    status: statusOf('risk_tools'),
    visual: MiniRisk,
  },
  {
    icon: Newspaper,
    title: 'Market context and events',
    text: 'Trading sessions and an event panel that ties items to instruments. The backend collects news; the web client shows labelled sample items until it is connected.',
    status: 'backend',
    visual: MiniNews,
  },
  {
    icon: Bot,
    title: 'A research assistant that shows its sources',
    text: 'Ask what the model saw, what would invalidate it or what a plan means for an account. Today it is a rule-based demo, and it says so.',
    status: statusOf('assistant'),
    visual: MiniAssistant,
  },
  {
    icon: Gauge,
    title: 'Evaluation you can inspect',
    text: 'Hit rate, Brier score and calibration, each defined, so you can judge how well stated probabilities match outcomes.',
    status: statusOf('analytics'),
    visual: MiniCalibration,
  },
];

function Capabilities() {
  return (
    <section id="capabilities" data-section aria-labelledby="capabilities-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <SectionHead eyebrow="02 · What the platform does" id="capabilities-title" lines={['Six capabilities,', <em key="e">one workflow.</em>]}>
          Each capability shows what it is based on and how far along it is: working now, running on simulated data, or waiting for a backend connection.
        </SectionHead>
        <ul className="mt-14 grid grid-cols-[minmax(0,1fr)] gap-5 md:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((c, i) => (
            <Reveal as="li" key={c.title} index={i} stagger={80} className="group flex flex-col rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-line-strong">
              <div className="flex items-start justify-between gap-3">
                <span className="inline-flex size-9 items-center justify-center rounded-full border border-line-strong text-accent">
                  <c.icon aria-hidden className="size-4" />
                </span>
                <StatusBadge status={c.status} />
              </div>
              <h3 className="mt-4 text-md font-semibold text-fg">{c.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-fg-2">{c.text}</p>
              <InViewPlay className="mt-5 h-32 rounded-xl border border-line bg-inset p-3 transition-transform duration-300 group-hover:-translate-y-0.5">
                <c.visual />
              </InViewPlay>
            </Reveal>
          ))}
        </ul>
        <p className="mt-6 text-xs text-fg-3">All previews use the platform’s simulated demo data at a fixed example time.</p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- 4. Workflow */

const STEPS = [
  { title: 'Market context', text: 'Which sessions are open and what is scheduled.', where: 'Market intelligence' },
  { title: 'News and events', text: 'Items tied to the instruments they affect.', where: 'Sample content today' },
  { title: 'Technical analysis', text: 'Candles, indicators and the NOW boundary.', where: 'Workspace' },
  { title: 'Signal and zones', text: 'Direction, probability, entry, stop, target.', where: 'AI research' },
  { title: 'Risk assessment', text: 'Size and loss at the stop for your limits.', where: 'Capital & risk' },
  { title: 'Structured research', text: 'Evidence, invalidation and what is missing.', where: 'Research plan' },
  { title: 'Your decision', text: 'The platform never places a trade.', where: 'You' },
];

function Workflow() {
  return (
    <section id="workflow" data-section aria-labelledby="workflow-title" className="overflow-hidden border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <SectionHead eyebrow="03 · How it works" id="workflow-title" lines={['From observation', <em key="e">to a decision you can explain.</em>]}>
          Seven steps, in the order a careful trader would take them. Each one hands its result to the next.
        </SectionHead>
        <InViewPlay className="relative mt-16">
          {/* Track and a travelling data point (desktop) */}
          <div aria-hidden className="absolute top-[22px] right-[7%] left-[7%] hidden h-px bg-line lg:block">
            <span className="m-grow-x block h-full origin-left bg-accent/70" style={{ ...at(200), '--m-slow': '2400ms' } as CSSProperties} />
            <span className="travel-track absolute inset-0" style={at(200)}>
              <span className="absolute -top-[3px] left-0 h-[7px] w-7 -translate-x-1/2 rounded-full bg-accent shadow-[0_0_14px_var(--accent)]" />
            </span>
          </div>
          <ol className="relative grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-7 lg:gap-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="m-in relative flex gap-4 lg:flex-col lg:items-center lg:gap-3 lg:text-center" style={at(300 + i * 280)}>
                <span
                  className={cn(
                    'num relative z-[1] inline-flex size-11 shrink-0 items-center justify-center rounded-full border bg-canvas text-sm',
                    i === STEPS.length - 1 ? 'border-fg text-fg' : 'border-accent text-accent',
                  )}
                >
                  {i === STEPS.length - 1 ? <UserRound aria-hidden className="size-4" /> : i + 1}
                </span>
                {i < STEPS.length - 1 && <span aria-hidden className="absolute top-11 bottom-[-1.5rem] left-[21px] w-px bg-line lg:hidden" />}
                <div>
                  <p className="text-sm font-semibold text-fg">{s.title}</p>
                  <p className="mt-1 text-xs leading-5 text-fg-2">{s.text}</p>
                  <p className="mt-1.5 text-[0.6875rem] tracking-wide text-fg-3 uppercase">{s.where}</p>
                </div>
              </li>
            ))}
          </ol>
        </InViewPlay>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------- 5. Approach to AI */

const PRINCIPLES = [
  { title: 'Evidence before conclusions', text: 'A model output is shown with the factors that produced it, the checks it passes and the conditions that would invalidate it.' },
  { title: 'Observed is never mixed with projected', text: 'History is drawn solid; anything the model projects is dashed, violet and to the right of NOW — and only where it supplied points.' },
  { title: 'Every answer names its sources', text: 'The assistant lists what it used and says plainly what it could not see: news, liquidity, anything off screen.' },
  { title: 'Honest about what is running', text: 'Today the assistant is rule-based and demo signals come from a browser heuristic. The interfaces are ready for the trained model and a real provider, with keys held on the server.' },
  { title: 'Probabilities, not promises', text: '“70 %” is an estimate that the target comes before the stop, with a band. It is evaluated publicly — not presented as certainty.' },
];

function ApproachAi() {
  const s = buildShowcase();
  const o = s.opportunity;
  const top = [...o.factors].sort((a, b) => b.contribution - a.contribution);
  const nodes = [
    { label: 'Model output', value: `${formatPercent(o.probability)} ${o.direction}` },
    { label: 'Factors', value: `${o.factors.length} attached` },
    { label: 'Your checks', value: `${s.evaluation.passed} of ${s.evaluation.checks.length} pass` },
    { label: 'Missing', value: `${s.missing.length} items` },
  ];
  const summary = [
    { k: 'Supports', v: top[0]?.label ?? '—' },
    { k: 'Weighs against', v: top.find((f) => f.contribution < 0)?.label ?? 'No opposing factor attached' },
    { k: 'Invalidated if', v: s.invalidation[0]?.title ?? '—' },
    { k: 'Still missing', v: s.missing[0]?.title ?? '—' },
  ];
  return (
    <section id="approach-ai" data-section aria-labelledby="approach-ai-title" className="violet-scene border-b border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] gap-14 px-5 py-24 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:items-center">
        <div>
          <SectionHead eyebrow="04 · Our approach to AI" id="approach-ai-title" lines={['Intelligence is', <em key="e">knowing what you don’t know.</em>]} />
          <ul className="mt-8 flex flex-col gap-5">
            {PRINCIPLES.map((p, i) => (
              <Reveal as="li" key={p.title} index={i} stagger={70} className="flex gap-4">
                <span aria-hidden className="mt-1 inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-forecast/40 text-forecast">
                  <Check className="size-3.5" />
                </span>
                <span>
                  <span className="block text-md font-medium text-fg">{p.title}</span>
                  <span className="mt-0.5 block text-sm leading-6 text-fg-2">{p.text}</span>
                </span>
              </Reveal>
            ))}
          </ul>
        </div>

        {/* Evidence → summary, assembled progressively */}
        <InViewPlay className="rounded-3xl border border-forecast/30 bg-surface/95 p-5 shadow-float">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-fg">How a research summary is assembled</p>
            <SourceTag kind="demo" className="ml-auto" />
          </div>
          <div className="mt-5 grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-[minmax(0,180px)_40px_minmax(0,1fr)] sm:items-center">
            <ul className="flex flex-col gap-2" aria-label="Inputs">
              {nodes.map((n, i) => (
                <li key={n.label} className="m-in rounded-xl border border-forecast/30 bg-forecast-soft px-3 py-2" style={at(i * 130)}>
                  <p className="text-[0.6875rem] tracking-wide text-fg-3 uppercase">{n.label}</p>
                  <p className="num text-sm text-fg">{n.value}</p>
                </li>
              ))}
            </ul>
            <svg aria-hidden viewBox="0 0 40 240" preserveAspectRatio="none" className="hidden h-60 w-full sm:block">
              {nodes.map((_, i) => (
                <path
                  key={i}
                  d={`M0 ${30 + i * 60} C24 ${30 + i * 60}, 18 120, 40 120`}
                  fill="none"
                  pathLength={1}
                  vectorEffect="non-scaling-stroke"
                  className="m-draw stroke-forecast"
                  strokeOpacity="0.6"
                  strokeWidth="1"
                  style={{ '--at': `${600 + i * 90}ms`, '--dur': '600ms', '--len': 1 } as CSSProperties}
                />
              ))}
            </svg>
            <div className="m-stage rounded-xl border border-line-strong bg-canvas p-4" style={at(1000)}>
              <p className="text-xs font-medium tracking-wide text-fg-2 uppercase">Research summary · {getInstrument(SHOWCASE_SYMBOL).display}</p>
              <dl className="mt-3 flex flex-col gap-2 text-sm">
                {summary.map((r, i) => (
                  <div key={r.k} className="m-in" style={at(1200 + i * 220)}>
                    <dt className="text-xs text-fg-3">{r.k}</dt>
                    <dd className="text-fg">{r.v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
          <p className="mt-4 text-xs text-fg-3">Assembled by fixed rules from simulated data — the same way the rule-based assistant works today.</p>
        </InViewPlay>
      </div>
    </section>
  );
}

/* ---------------------------------------------- 6. Risk, transparency, uncertainty */

const RISK_OPTIONS = [
  { value: '0.5', label: '0.5 %' },
  { value: '1', label: '1 %' },
  { value: '2', label: '2 %' },
] as const;

function RiskTransparency() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const [pct, setPct] = useState<'0.5' | '1' | '2'>('1');
  const result = useMemo(() => computeTradeRisk(SHOWCASE_PROFILE, { instrument: inst, ...s.plan, riskPct: Number(pct), quoteToAccountRate: null }), [inst, s.plan, pct]);
  const r = result.kind === 'ok' ? result.risk : null;
  const o = s.opportunity;
  const band = o.confidenceBand;

  return (
    <section id="risk-transparency" data-section aria-labelledby="risk-transparency-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <SectionHead eyebrow="05 · Risk, transparency and uncertainty" id="risk-transparency-title" lines={['Uncertainty is information.', <em key="e">We show it.</em>]}>
          Every analysis can be wrong, so the platform puts the size of a possible loss, the uncertainty of the estimate and the origin of every number in plain view.
        </SectionHead>
        <div className="mt-14 grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-3">
          {/* Risk */}
          <Reveal className="flex flex-col rounded-2xl border border-line bg-surface p-5">
            <p className="flex items-center gap-2 text-md font-semibold text-fg">
              <Scale aria-hidden className="size-4 text-accent" /> Risk, before the trade
            </p>
            <p className="mt-1.5 text-sm text-fg-2">The same calculator as the app, on the example plan and a $25,000 example account.</p>
            <SegmentedControl label="Risk per trade" value={pct} options={RISK_OPTIONS} onChange={setPct} className="mt-4 self-start" />
            <div className="mt-4 flex items-center gap-4">
              <div className="w-36 shrink-0">
                <ExposureGauge pct={Number(pct)} />
              </div>
              {r && (
                <dl aria-live="polite" className="grid gap-1.5 text-sm">
                  <div>
                    <dt className="text-xs text-fg-3">Loss if the stop is hit</dt>
                    <dd className="num text-lg text-down">{formatMoney(r.monetaryRisk, 'USD')}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-fg-3">Position</dt>
                    <dd className="num text-fg">{formatUnits(r.units, inst.base)}</dd>
                  </div>
                </dl>
              )}
            </div>
            <p className="mt-auto pt-4 text-xs text-fg-3">A stop is an instruction, not a guarantee: gaps and slippage can make the loss larger.</p>
          </Reveal>

          {/* Uncertainty */}
          <Reveal delay={90} className="flex flex-col rounded-2xl border border-line bg-surface p-5">
            <p className="flex items-center gap-2 text-md font-semibold text-fg">
              <Gauge aria-hidden className="size-4 text-forecast" /> Uncertainty, stated
            </p>
            <p className="mt-1.5 text-sm text-fg-2">
              The example signal says {formatPercent(o.probability)}{band ? `, band ${formatProbabilityBand(band)}` : ''}: an estimate that the target is reached before the
              stop.
            </p>
            <InViewPlay className="mt-6">
              <div aria-hidden className="relative h-3 rounded-full bg-line">
                {band && (
                  <span
                    className="m-fade absolute inset-y-0 rounded-full bg-forecast/30"
                    style={{ left: `${band.low * 100}%`, width: `${(band.high - band.low) * 100}%`, ...at(200) }}
                  />
                )}
                <span className="m-pop absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-forecast" style={{ left: `${o.probability * 100}%`, ...at(400) }} />
              </div>
              <div className="mt-2 flex justify-between text-xs text-fg-3">
                <span className="num">0 %</span>
                <span className="num">50 %</span>
                <span className="num">100 %</span>
              </div>
            </InViewPlay>
            <p className="mt-5 text-sm text-fg-2">
              If estimates like this are well calibrated, about {Math.round((1 - o.probability) * 10)} in 10 such setups still reach the stop first. Calibration is measured,
              not assumed.
            </p>
            <p className="mt-auto pt-4 text-xs text-fg-3">No verified live results exist yet; published figures come from simulated history.</p>
          </Reveal>

          {/* Transparency */}
          <Reveal delay={180} className="flex flex-col rounded-2xl border border-line bg-surface p-5">
            <p className="flex items-center gap-2 text-md font-semibold text-fg">
              <FileText aria-hidden className="size-4 text-accent" /> Every number, labelled
            </p>
            <p className="mt-1.5 text-sm text-fg-2">Each figure carries one of these labels, so you always know what you are looking at.</p>
            <ul className="mt-4 flex flex-col gap-2.5">
              {SOURCE_DEFINITIONS.filter((d) => d.kind !== 'historical').map((d) => (
                <li key={d.kind} className="flex flex-col gap-1">
                  <SourceTag kind={d.kind} className="self-start" />
                  <span className="text-xs leading-5 text-fg-2">{d.detail}</span>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------ 7. Audience */

const AUDIENCES = [
  {
    title: 'Gold traders who want structure',
    text: 'XAU/USD is the platform’s first instrument. You get one place for the chart, the model’s view, its evidence and the size of the trade.',
    detail: 'Gold workspace · zones · sizing in ounces',
  },
  {
    title: 'Traders who compare before they commit',
    text: 'Seven FX majors besides gold, and 15m, 1h and 4h analyses side by side, so disagreement between timeframes is visible instead of hidden.',
    detail: 'Multi-timeframe alignment · personalised signal checks',
  },
  {
    title: 'Anyone who sizes before they act',
    text: 'If you want every idea measured against your capital, risk per trade and daily limits before you decide, the risk tools work on your inputs alone.',
    detail: 'Capital & risk · limit checks · no guessed broker details',
  },
];
const NOT_FOR = ['Copying signals without reading them', 'Automated execution — it never places trades', 'Anyone looking for guaranteed returns'];

function Audience() {
  return (
    <section id="audience" data-section aria-labelledby="audience-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <SectionHead eyebrow="06 · Who it is for" id="audience-title" lines={['Built for traders', <em key="e">who do the reading.</em>]} />
        <ol className="mt-12 flex flex-col divide-y divide-line border-y border-line">
          {AUDIENCES.map((a, i) => (
            <Reveal
              as="li"
              key={a.title}
              index={i}
              stagger={90}
              className="group grid grid-cols-[minmax(0,1fr)] gap-3 py-8 transition-colors sm:grid-cols-[96px_minmax(0,1fr)_minmax(0,260px)] sm:items-baseline sm:gap-8"
            >
              <span className="display text-d2 leading-none text-fg-3 transition-colors group-hover:text-accent">0{i + 1}</span>
              <div>
                <h3 className="display text-d3 leading-tight text-fg">{a.title}</h3>
                <p className="mt-2 max-w-xl text-sm leading-6 text-fg-2">{a.text}</p>
              </div>
              <p className="text-xs tracking-wide text-fg-3 uppercase">{a.detail}</p>
            </Reveal>
          ))}
        </ol>
        <Reveal className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <p className="text-sm font-medium text-fg">Not built for</p>
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {NOT_FOR.map((n) => (
              <li key={n} className="flex items-center gap-2 text-sm text-fg-2">
                <Ban aria-hidden className="size-3.5 text-fg-3" /> {n}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- 8. Closing */

function AboutClosing() {
  return (
    <section aria-labelledby="about-cta-title" className="relative isolate overflow-hidden border-b border-line">
      <div aria-hidden className="footage-band footage-dim pointer-events-none absolute inset-0 -z-10">
        <CinematicVideo {...FOOTAGE.method} />
        <div className="footage-veil absolute inset-0" />
      </div>
      <div aria-hidden className="footage-pool pointer-events-none absolute inset-0 -z-10" />
      <div className="mx-auto flex max-w-[1240px] flex-col items-center px-5 py-32 text-center sm:px-8">
        <p className="eyebrow mb-4">Next step</p>
        <RevealText as="h2" id="about-cta-title" className="display text-d2 text-fg sm:text-d1" lines={['Discipline is a process.', <em key="e">This is the process.</em>]} />
        <Reveal as="p" delay={180} className="mt-5 max-w-xl text-md text-fg-2">
          Walk through the workflow on simulated data, compare the plans, or create an account. Pricing has not been announced and no payment is taken.
        </Reveal>
        <Reveal delay={300} className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to="/#platform" viewTransition className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill' })}>
            Explore the platform <ArrowRight aria-hidden className="size-4" />
          </Link>
          <Link to="/membership" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
            View membership
          </Link>
          <Link to="/register" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
            Create an account
          </Link>
        </Reveal>
      </div>
    </section>
  );
}

export function AboutPage() {
  useDocumentMeta({
    title: 'About',
    description:
      'Why we are building a structured research platform for gold and FX, how its workflow and AI-assisted research work, and how it treats evidence, uncertainty and risk.',
    path: '/about',
  });
  return (
    <>
      <AboutHero />
      <ProblemScene />
      <Capabilities />
      <Workflow />
      <ApproachAi />
      <RiskTransparency />
      <Audience />
      <AboutClosing />
    </>
  );
}
