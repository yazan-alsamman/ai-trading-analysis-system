import { CircleCheck, CircleDashed, CircleX, Newspaper } from 'lucide-react';
import { useRef, type CSSProperties } from 'react';
import { Badge } from '@/components/ui/Badge';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { sessionStates, sessionSummary } from '@/domain/sessions';
import { buildDemoNews } from '@/fixtures/community';
import { cn } from '@/lib/cn';
import { formatDateTime, formatPercent, formatPrice, formatProbabilityBand, formatRiskReward } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useInView } from '@/motion/runtime';
import { buildShowcase, SHOWCASE_ANCHOR, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const at = (ms: number) => ({ '--at': `${ms}ms` }) as CSSProperties;
const ICON = { pass: CircleCheck, fail: CircleX, not_evaluated: CircleDashed } as const;

const W = 640;
const H = 330;
const AXIS = 92;
const PAD = 18;

/**
 * The entry zone in its price structure: the simulated candles, then the
 * model's three zones as bands from the signal candle, then the distances
 * that make up reward : risk. No future path is drawn here.
 */
function ZoneChart() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const o = s.opportunity;
  const candles = s.candles.slice(-36);
  const first = candles[0];
  const last = candles[candles.length - 1];
  if (!first || !last) return null;
  const zones = [
    { key: 'Target', z: o.takeProfitZone, fill: 'fill-up', stroke: 'stroke-up', text: 'fill-up' },
    { key: 'Entry', z: o.entryZone, fill: 'fill-accent', stroke: 'stroke-accent', text: 'fill-accent' },
    { key: 'Stop', z: o.stopLossZone, fill: 'fill-down', stroke: 'stroke-down', text: 'fill-down' },
  ];
  const values = [...candles.flatMap((c) => [c.high, c.low]), ...zones.flatMap((z) => [z.z.low, z.z.high])];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo) * 0.06;
  const plotW = W - AXIS;
  // History takes ~70 % of the width; the zones extend into the space after the signal candle.
  const step = (plotW * 0.7) / candles.length;
  const x = (i: number) => 10 + i * step;
  const y = (v: number) => PAD + (1 - (v - (lo - pad)) / (hi + pad - (lo - pad))) * (H - 2 * PAD);
  const sigIndex = Math.max(0, candles.findIndex((c) => c.time >= o.signalCandleTime));
  const zx = x(sigIndex);
  const entry = (o.entryZone.low + o.entryZone.high) / 2;
  const stop = (o.stopLossZone.low + o.stopLossZone.high) / 2;
  const target = (o.takeProfitZone.low + o.takeProfitZone.high) / 2;
  const bx = plotW - 30;
  // Two-line labels (~28 px) are pushed apart so they never overlap.
  const labelY = new Map<string, number>();
  [...zones]
    .sort((a, b) => y((a.z.low + a.z.high) / 2) - y((b.z.low + b.z.high) / 2))
    .reduce((prev, z) => {
      const ly = Math.max(y((z.z.low + z.z.high) / 2), prev + 30);
      labelY.set(z.key, ly);
      return ly;
    }, -Infinity);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Simulated ${inst.display} ${SHOWCASE_TIMEFRAME} candles with the demo model's entry, stop and target zones drawn from the signal candle.`} className="h-auto w-full">
      {candles.map((c, i) => {
        const up = c.close >= c.open;
        return (
          <g key={c.time} className={cn('m-fade', up ? 'fill-up stroke-up' : 'fill-down stroke-down')} style={at(i * 18)}>
            <line x1={x(i)} x2={x(i)} y1={y(c.high)} y2={y(c.low)} strokeWidth="1" />
            <rect x={x(i) - step * 0.3} y={Math.min(y(c.open), y(c.close))} width={step * 0.6} height={Math.max(1.5, Math.abs(y(c.open) - y(c.close)))} rx="1" strokeWidth="0" />
          </g>
        );
      })}
      {/* Zones grow from the signal candle */}
      {zones.map((z, i) => (
        <g key={z.key}>
          <rect
            x={zx}
            y={y(z.z.high)}
            width={plotW - zx}
            height={Math.max(3, y(z.z.low) - y(z.z.high))}
            className={cn('m-grow-x', z.fill)}
            fillOpacity="0.16"
            style={at(800 + i * 160)}
          />
          <line x1={zx} x2={plotW} y1={y((z.z.low + z.z.high) / 2)} y2={y((z.z.low + z.z.high) / 2)} className={cn('m-fade', z.stroke)} strokeDasharray="5 5" strokeWidth="1.2" style={at(900 + i * 160)} />
          <text x={plotW + 8} y={(labelY.get(z.key) ?? 0) - 2} fontSize="12" className={cn('num m-fade', z.text)} style={at(1000 + i * 160)}>
            {z.key}
          </text>
          <text x={plotW + 8} y={(labelY.get(z.key) ?? 0) + 12} fontSize="11" className="num m-fade fill-fg-3" style={at(1000 + i * 160)}>
            {formatPrice((z.z.low + z.z.high) / 2, inst.pricePrecision)}
          </text>
        </g>
      ))}
      <line x1={zx} x2={zx} y1={PAD - 6} y2={H - PAD} className="m-fade stroke-fg-3" strokeDasharray="2 4" style={at(700)} />
      <text x={zx + 4} y={H - 4} fontSize="11" className="m-fade fill-fg-3" style={at(700)}>
        signal candle
      </text>
      {/* Distances: risk (entry → stop) and reward (entry → target) */}
      <g className="m-fade" style={at(1500)}>
        <path d={`M${bx} ${y(entry)} L${bx} ${y(stop)}`} className="stroke-down" strokeWidth="2" />
        <path d={`M${bx - 16} ${y(entry)} L${bx} ${y(entry)} M${bx - 16} ${y(stop)} L${bx} ${y(stop)}`} className="stroke-down" strokeWidth="1" />
        <path d={`M${bx - 22} ${y(entry)} L${bx - 22} ${y(target)}`} className="stroke-up" strokeWidth="2" />
        <text x={bx - 28} y={(y(entry) + y(target)) / 2 + 4} fontSize="11" textAnchor="end" className="num fill-up">
          reward
        </text>
        <text x={bx - 22} y={y(stop) - 6} fontSize="11" textAnchor="end" className="num fill-down">
          risk
        </text>
      </g>
    </svg>
  );
}

const NOTES = [
  'An entry zone is an area of interest, not a guaranteed fill.',
  'The stop zone is where the analysis stops applying — not a cap on what you can lose. Gaps and slippage exist.',
  'A target zone may never be reached. The probability says how often the model expects it to be.',
];

/**
 * Scene: the anatomy of one setup — signal, zones in their price structure,
 * the checks it passes, and the market context around it (sample items, as
 * the web client is not yet connected to the backend news service).
 */
export function AnatomySection() {
  const s = buildShowcase();
  const o = s.opportunity;
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const p = (v: number) => formatPrice(v, inst.pricePrecision);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartIn = useInView(chartRef, { threshold: 0.3 });
  const anchorMs = SHOWCASE_ANCHOR * 1000;
  const news = buildDemoNews(anchorMs).filter((n) => n.symbols.includes(SHOWCASE_SYMBOL) || n.impact === 'high').slice(0, 2);
  const checks = s.evaluation.checks.slice(0, 4);

  return (
    <section id="anatomy" data-section aria-labelledby="anatomy-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:items-end">
          <div>
            <p className="eyebrow mb-3">05 · Anatomy of a setup</p>
            <RevealText as="h2" id="anatomy-title" className="display text-d3 text-fg sm:text-d2" lines={['One signal,', <em key="e">taken apart.</em>]} />
            <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
              What a model signal contains, where its zones sit in the price structure, the checks it passes and the context around it — shown on one simulated example,
              not a current recommendation.
            </Reveal>
          </div>
          <Reveal as="ul" delay={200} className="flex flex-col gap-2 text-sm text-fg-2">
            {NOTES.map((n) => (
              <li key={n} className="flex gap-2">
                <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-accent" />
                {n}
              </li>
            ))}
          </Reveal>
        </div>

        <div className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
          {/* Zones in context */}
          <figure ref={chartRef} data-play={chartIn} className="overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-float">
            <figcaption className="flex items-center gap-2 border-b border-line px-4 py-3">
              <span className="text-sm font-semibold text-fg">{inst.display}</span>
              <span className="text-sm text-fg-3">· {SHOWCASE_TIMEFRAME} · zones from the signal candle</span>
              <SourceTag kind="demo" className="ml-auto" />
            </figcaption>
            <div className="px-3 pt-3 pb-2">
              <ZoneChart />
            </div>
          </figure>

          {/* The signal, structured */}
          <Reveal variant="right" className="flex flex-col rounded-2xl border border-line-strong bg-surface p-5 shadow-float">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-fg">{inst.display}</span>
              <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
              <DirectionBadge direction={o.direction} />
              <SourceTag kind="demo" className="ml-auto" />
            </div>
            <p className="mt-1 text-xs text-fg-3">
              Generated {formatDateTime(o.generatedAt, 'UTC')} UTC · valid for {o.horizonCandles} candles · example time
            </p>
            <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
              <dt className="text-fg-3">Entry zone</dt>
              <dd className="num text-accent">
                {p(o.entryZone.low)} – {p(o.entryZone.high)}
              </dd>
              <dt className="text-fg-3">Stop (invalidation)</dt>
              <dd className="num text-down">
                {p(o.stopLossZone.low)} – {p(o.stopLossZone.high)}
              </dd>
              <dt className="text-fg-3">Target zone</dt>
              <dd className="num text-up">
                {p(o.takeProfitZone.low)} – {p(o.takeProfitZone.high)}
              </dd>
              <dt className="text-fg-3">Reward : risk</dt>
              <dd className="num text-fg">{formatRiskReward(o.riskReward)}</dd>
              <dt className="text-fg-3">Probability</dt>
              <dd className="num text-forecast">
                {formatPercent(o.probability)}
                {o.confidenceBand && <span className="text-fg-3"> · band {formatProbabilityBand(o.confidenceBand)}</span>}
              </dd>
            </dl>
            <p className="mt-4 border-t border-line pt-3 text-xs font-medium tracking-wide text-fg-2 uppercase">Checks against a saved profile</p>
            <ul className="mt-2 flex flex-col gap-1.5">
              {checks.map((c, i) => {
                const Icon = ICON[c.status];
                return (
                  <Reveal as="li" key={c.id} index={i} stagger={90} delay={300} variant="left" className="flex gap-2 text-sm">
                    <Icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', c.status === 'pass' ? 'text-accent' : c.status === 'fail' ? 'text-danger' : 'text-fg-3')} />
                    <span className="text-fg">{c.label}</span>
                  </Reveal>
                );
              })}
            </ul>
            <p className="mt-auto pt-4 text-xs text-fg-3">A probability is an estimate, not a forecast that will come true.</p>
          </Reveal>
        </div>

        {/* Market context */}
        <Reveal className="mt-5 grid grid-cols-[minmax(0,1fr)] gap-5 rounded-2xl border border-line bg-surface p-5 md:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
          <div>
            <p className="flex items-center gap-2 text-md font-semibold text-fg">
              <Newspaper aria-hidden className="size-4 text-accent" /> Market context
            </p>
            <p className="mt-1.5 text-xs leading-5 text-fg-2">
              How context is organised around a setup. The backend collects news from RSS sources; the web client is not connected to it yet, so these are labelled sample
              items, not headlines.
            </p>
            <p className="eyebrow mt-4">Sessions at the example time</p>
            <p className="mt-1 text-xs text-fg-2">{sessionSummary(anchorMs)}</p>
            <ul className="mt-2 grid grid-cols-4 gap-1.5">
              {sessionStates(anchorMs).map((st) => (
                <li key={st.id} className={cn('rounded-md border px-1.5 py-1 text-center text-[0.6875rem]', st.open ? 'border-accent/50 bg-accent-soft text-fg' : 'border-line text-fg-3')}>
                  {st.label}
                </li>
              ))}
            </ul>
          </div>
          <ul className="flex flex-col divide-y divide-line">
            {news.map((n) => (
              <li key={n.id} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={n.impact === 'high' ? 'warning' : 'neutral'}>{n.impact} impact</Badge>
                  <SourceTag kind="demo" label="Sample content" />
                  <span className="text-xs text-fg-3">Relevant to: {n.symbols.map((sym) => getInstrument(sym).display).join(' · ')}</span>
                </div>
                <p className="text-sm text-fg">{n.title}</p>
                <p className="text-xs text-fg-3">{n.summary}</p>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}
