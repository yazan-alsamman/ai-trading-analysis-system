import { Ban, Clock, FileSearch, Gauge, Scale, ScanSearch, TriangleAlert } from 'lucide-react';
import { useRef, useState, type CSSProperties } from 'react';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatDate, formatDateTime, formatMoney, formatNumber, formatPercent, formatRiskReward } from '@/lib/format';
import { CinematicVideo } from '@/motion/CinematicVideo';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useInView } from '@/motion/runtime';
import { FOOTAGE } from '../media';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';
import { buildDemoPredictionHistory } from '@/fixtures/predictions';

const DEFINITIONS = [
  ['Hit rate', 'Resolved predictions whose target was reached before the stop, divided by all resolved predictions.'],
  ['Brier score', 'Mean of (stated probability − outcome)². 0 is perfect; always answering 50 % scores 0.25.'],
  ['Calibration', 'Predictions grouped by stated probability and compared with how often they came true.'],
  ['Realised R', 'Result per prediction in units of risk: + reward : risk at the target, −1 at the stop.'],
] as const;

/** Reliability diagram geometry (viewBox units). */
const RX0 = 40;
const RX1 = 312;
const RY0 = 12;
const RY1 = 172;
const rx = (v: number) => RX0 + v * (RX1 - RX0);
const ry = (v: number) => RY1 - v * (RY1 - RY0);

const NEVER = ['Win-rate or profit promises', 'Testimonials or member counts', 'Backtests presented as live results', 'Probabilities without definitions'];

export function EvidenceSection() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const o = s.opportunity;
  const [view, setView] = useState<'summary' | 'evidence'>('evidence');
  const facetsRef = useRef<HTMLDivElement>(null);
  const facetsIn = useInView(facetsRef);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartIn = useInView(chartRef);
  const history = buildDemoPredictionHistory(o.generatedAt);
  const resolvedTimes = history.filter((h) => h.outcome !== 'open').map((h) => h.generatedAt);
  const from = Math.min(...resolvedTimes);
  const to = Math.max(...resolvedTimes);
  const top = [...o.factors].sort((a, b) => b.contribution - a.contribution)[0];

  const facets = [
    { icon: FileSearch, title: 'Source', text: `Model ${o.modelVersion}. In demo mode a browser heuristic stands in for the trained model.`, tag: <SourceTag kind="demo" /> },
    { icon: Clock, title: 'When it was generated', text: `${formatDateTime(o.generatedAt, 'UTC')} UTC, valid for ${o.horizonCandles} candles. Older analyses are flagged stale.` },
    { icon: ScanSearch, title: 'Supporting evidence', text: `${o.factors.length} contributing factors, the strongest: “${top?.label ?? '—'}”.` },
    { icon: TriangleAlert, title: 'Limitations', text: `${s.missing.length} items missing or unverified — e.g. ${s.missing.slice(0, 2).map((m) => m.title.toLowerCase()).join('; ')}.` },
    { icon: Scale, title: 'Risk implications', text: `At $25,000 and 1 % risk: ${formatMoney(s.risk.monetaryRisk, 'USD')} lost if the stop is hit.`, tag: <SourceTag kind="user" label="Example" /> },
    { icon: Gauge, title: 'Historical evaluation', text: `Hit rate ${formatPercent(s.stats.hitRate)}, Brier ${formatNumber(s.stats.brierScore, 3)} over ${s.stats.resolved} resolved predictions.`, tag: <SourceTag kind="demo" label="Simulated history" /> },
  ];
  const bins = s.stats.calibration.filter((b) => b.count > 0);

  return (
    <section id="methodology" data-section aria-labelledby="evidence-title" className="relative isolate overflow-hidden border-b border-line">
      {/* Footage: notes being written by hand — the method, not a result. */}
      <div aria-hidden className="footage-band footage-dim pointer-events-none absolute inset-x-0 top-0 -z-10 h-[620px]">
        <CinematicVideo {...FOOTAGE.method} />
        <div className="footage-veil absolute inset-0" />
        <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/85 to-canvas/10" />
      </div>
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <p className="eyebrow mb-3">08 · Performance &amp; methodology</p>
        <RevealText as="h2" id="evidence-title" className="display max-w-3xl text-d3 text-fg sm:text-d2" lines={['Don’t trust a signal.', <em key="e">Inspect it.</em>]} />
        <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
          Every result can be opened from its one-line summary into the evidence behind it: where it came from, when, why, what it cannot see, what it means for your money,
          and how the model has done before.
        </Reveal>

        {/* Sequence D: summary → evidence */}
        <div className="mt-12 flex flex-col items-center">
          <div role="tablist" aria-label="Level of detail" className="inline-flex rounded-full border border-line bg-surface p-1">
            {(['summary', 'evidence'] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={cn('h-8 rounded-full px-4 text-sm font-medium capitalize transition-colors duration-150', view === v ? 'bg-primary text-primary-fg' : 'text-fg-2 hover:text-fg')}
              >
                {v}
              </button>
            ))}
          </div>

          <Reveal variant="scale" className="relative z-[1] mt-8 w-full max-w-md rounded-2xl border border-line-strong bg-surface p-5 shadow-float">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-fg">{inst.display}</span>
              <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
              <DirectionBadge direction={o.direction} />
              <SourceTag kind="demo" className="ml-auto" />
            </div>
            <p className="mt-3 flex items-baseline gap-2">
              <span className="num text-d3 leading-none text-forecast">{formatPercent(o.probability)}</span>
              <span className="text-sm text-fg-2">target before stop · {formatRiskReward(o.riskReward)}</span>
            </p>
          </Reveal>

          <div ref={facetsRef} className="relative w-full" data-play={facetsIn && view === 'evidence'}>
            {/* Connectors from the summary card to each facet */}
            <svg aria-hidden viewBox="0 0 1200 60" preserveAspectRatio="none" className={cn('hidden h-14 w-full transition-opacity duration-300 lg:block', view === 'summary' && 'opacity-0')}>
              {[100, 300, 500, 700, 900, 1100].map((xEnd, i) => (
                <path
                  key={xEnd}
                  d={`M600 0 C600 30, ${xEnd} 30, ${xEnd} 60`}
                  fill="none"
                  pathLength={1}
                  vectorEffect="non-scaling-stroke"
                  className="m-draw stroke-line-strong"
                  strokeWidth="1"
                  style={{ '--at': `${i * 70}ms`, '--dur': '700ms', '--len': 1 } as CSSProperties}
                />
              ))}
            </svg>
            <div className={cn('accordion-panel mt-6 lg:mt-0')} data-open={view === 'evidence'}>
              <div>
                <ul className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 lg:grid-cols-6" aria-label="Evidence behind the result">
                  {facets.map((f, i) => (
                    <li key={f.title} className="m-in flex flex-col gap-2 rounded-xl border border-line bg-surface p-4" style={{ '--at': `${250 + i * 80}ms` } as CSSProperties}>
                      <span className="flex items-center justify-between gap-2">
                        <f.icon aria-hidden className="size-4 text-accent" />
                        {f.tag}
                      </span>
                      <span className="text-sm font-medium text-fg">{f.title}</span>
                      <span className="text-xs leading-5 text-fg-2">{f.text}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* Methodology */}
        <div className="mt-20 grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Reveal className="rounded-2xl border border-line bg-surface p-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-md font-semibold text-fg">How results are evaluated</p>
              <SourceTag kind="demo" label="Simulated data" />
            </div>
            <p className="mt-2 rounded-lg border border-dashed border-demo/50 bg-demo-soft px-3 py-2 text-sm text-fg-2">
              <strong className="font-semibold text-fg">No verified live results exist yet.</strong> The figures below are computed from simulated predictions to demonstrate
              the method. They say nothing about the accuracy of the real model.
            </p>
            <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <dt className="text-fg-3">Evaluation period</dt>
              <dd className="num text-fg">
                {formatDate(from, 'UTC')} – {formatDate(to, 'UTC')}
              </dd>
              <dt className="text-fg-3">Sample size</dt>
              <dd className="num text-fg">{s.stats.resolved} resolved predictions</dd>
              <dt className="text-fg-3">Data</dt>
              <dd className="text-fg">Simulated (browser fixtures)</dd>
              <dt className="text-fg-3">Hit rate · Brier</dt>
              <dd className="num text-fg">
                {formatPercent(s.stats.hitRate)} · {formatNumber(s.stats.brierScore, 3)}
              </dd>
            </dl>
            <dl className="mt-6 flex flex-col gap-3 border-t border-line pt-5">
              {DEFINITIONS.map(([term, def]) => (
                <div key={term}>
                  <dt className="text-sm font-medium text-fg">{term}</dt>
                  <dd className="text-xs text-fg-2">{def}</dd>
                </div>
              ))}
            </dl>
          </Reveal>

          <div className="flex flex-col gap-6">
            <Reveal delay={100} className="rounded-2xl border border-line bg-surface p-6">
              <p className="text-md font-semibold text-fg">Calibration</p>
              <p className="mt-1 text-xs text-fg-3">
                Each point is a probability band: what the model said (across) against how often it came true (up). On the diagonal, the stated probabilities were
                right. Simulated history.
              </p>
              <div ref={chartRef} data-play={chartIn} className="mt-4">
                <svg viewBox="0 0 320 200" aria-hidden className="h-auto w-full">
                  {/* Axes */}
                  <path d={`M${RX0} ${RY0} L${RX0} ${RY1} L${RX1} ${RY1}`} fill="none" pathLength={1} className="m-draw stroke-line-strong" strokeWidth="1" style={{ '--at': '0ms', '--dur': '700ms', '--len': 1 } as CSSProperties} />
                  {[0, 0.5, 1].map((v) => (
                    <g key={v} className="m-fade" style={{ '--at': '300ms' } as CSSProperties}>
                      <text x={rx(v)} y={RY1 + 14} fontSize="9" textAnchor="middle" className="num fill-fg-3">
                        {v * 100} %
                      </text>
                      <text x={RX0 - 6} y={ry(v) + 3} fontSize="9" textAnchor="end" className="num fill-fg-3">
                        {v * 100} %
                      </text>
                    </g>
                  ))}
                  <text x={(RX0 + RX1) / 2} y={RY1 + 26} fontSize="9" textAnchor="middle" className="fill-fg-3">
                    stated probability
                  </text>
                  {/* Perfect calibration */}
                  <path d={`M${rx(0)} ${ry(0)} L${rx(1)} ${ry(1)}`} fill="none" className="m-fade stroke-fg-3" strokeWidth="1" strokeDasharray="3 4" style={{ '--at': '500ms' } as CSSProperties} />
                  {/* Observed */}
                  <path
                    d={bins.map((b, i) => `${i ? 'L' : 'M'}${rx(b.meanPredicted).toFixed(1)} ${ry(b.observedRate).toFixed(1)}`).join(' ')}
                    fill="none"
                    pathLength={1}
                    className="m-draw stroke-forecast"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                    style={{ '--at': '800ms', '--dur': '1100ms', '--len': 1 } as CSSProperties}
                  />
                  {bins.map((b, i) => (
                    <circle
                      key={b.from}
                      cx={rx(b.meanPredicted)}
                      cy={ry(b.observedRate)}
                      r={Math.min(7, 2.5 + Math.sqrt(b.count))}
                      className="m-pop fill-forecast"
                      fillOpacity="0.85"
                      style={{ '--at': `${850 + i * 140}ms` } as CSSProperties}
                    />
                  ))}
                </svg>
                <ul className="sr-only">
                  {bins.map((b) => (
                    <li key={b.from}>
                      Stated {formatPercent(b.from)}–{formatPercent(b.to)}: came true {formatPercent(b.observedRate)} of {b.count} predictions.
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
            <Reveal delay={180} className="rounded-2xl border border-line bg-surface p-6">
              <p className="text-md font-semibold text-fg">What we will not show you</p>
              <ul className="mt-3 grid grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-2">
                {NEVER.map((n) => (
                  <li key={n} className="flex gap-2 text-sm text-fg-2">
                    <Ban aria-hidden className="mt-0.5 size-4 shrink-0 text-fg-3" /> {n}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}
