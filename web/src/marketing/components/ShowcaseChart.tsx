import { useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import type { Candle } from '@/domain/market';
import { timeframeSeconds, type Timeframe } from '@/domain/market';
import { zoneMid, type Opportunity } from '@/domain/opportunity';
import { cn } from '@/lib/cn';
import { formatDateTime, formatPrice } from '@/lib/format';

/**
 * The marketing chart: SIMULATED demo candles + the demo model's output.
 *
 * Layers appear in a fixed order that mirrors the research workflow:
 * observed history → NOW boundary → model projection (only the points the
 * model supplied, only to the right of NOW) → model levels.
 *
 *  - mode "intro": timed CSS sequence on first paint (hero): grid and time
 *    axis → history line draws → swing points → NOW → levels → projection.
 *  - mode "steps": layers switch on as `step` increases (scroll sequence C).
 */
export type ChartLayer = 'history' | 'now' | 'projection' | 'levels';

interface Props {
  candles: readonly Candle[];
  opportunity: Opportunity;
  timeframe: Timeframe;
  precision: number;
  variant?: 'line' | 'candles';
  mode?: 'intro' | 'steps';
  /** steps mode: which layers are visible. */
  visible?: readonly ChartLayer[];
  /** intro mode: ms offset for the whole sequence. */
  startAt?: number;
  className?: string;
  /** Accessible description of what is drawn. */
  label: string;
  /**
   * Ambient loop (hero): a crosshair steps through the simulated history with
   * a readout. Pass false while the chart is off-screen or motion is reduced.
   */
  scan?: boolean;
}

const W = 720;
const H = 380;
const PAD_T = 22;
const PAD_B = 30;
const AXIS = 86;
/** Hero intro: the crosshair starts once the intro has finished. */
const SCAN_START_MS = 3600;
const SCAN_STEP_MS = 1500;

/** Local swing highs/lows of the close (decorative data points along the drawn line). */
function swingPoints(candles: readonly Candle[], span = 5, max = 6): number[] {
  const out: number[] = [];
  candles.forEach((c, i) => {
    if (i < span || i >= candles.length - span) return;
    const win = candles.slice(i - span, i + span + 1).map((k) => k.close);
    if (c.close === Math.max(...win) || c.close === Math.min(...win)) out.push(i);
  });
  // Keep them spread out: drop any within `span` of the previous one.
  return out.filter((i, k) => k === 0 || i - (out[k - 1] ?? -Infinity) > span).slice(0, max);
}

/** Indices the hero crosshair visits, oldest to newest. */
function scanPath(n: number): number[] {
  const out: number[] = [];
  for (let i = 6; i < n; i += 5) out.push(i);
  if (out[out.length - 1] !== n - 1) out.push(n - 1);
  return out;
}

export function ShowcaseChart({ candles, opportunity: o, timeframe, precision, variant = 'line', mode = 'intro', visible = ['history', 'now', 'projection', 'levels'], startAt = 0, className, label, scan = false }: Props) {
  const gid = useId().replace(/:/g, '');
  const [scanAt, setScanAt] = useState(-1);
  const started = useRef(false);
  useEffect(() => {
    if (!scan) return;
    const path = scanPath(candles.length);
    let k = -1;
    let timer = 0;
    const advance = () => {
      started.current = true;
      k = (k + 1) % path.length;
      setScanAt(path[k] ?? -1);
      timer = window.setTimeout(advance, SCAN_STEP_MS);
    };
    // Wait for the intro until the first step has run; resume quickly when scanning is switched back on.
    timer = window.setTimeout(advance, started.current ? 300 : Math.max(0, startAt + SCAN_START_MS));
    return () => window.clearTimeout(timer);
  }, [scan, candles.length, startAt]);
  const last = candles[candles.length - 1];
  const first = candles[0];
  if (!last || !first) return null;
  const step = timeframeSeconds(timeframe);
  const forecast = (o.forecast ?? []).filter((f) => f.time > last.time);
  const tEnd = Math.max(last.time + Math.ceil(o.horizonCandles * 0.6) * step, forecast[forecast.length - 1]?.time ?? 0) + step;
  const levels = [
    { key: 'TP', label: 'Target', price: zoneMid(o.takeProfitZone), cls: 'stroke-up', text: 'fill-up' },
    { key: 'Entry', label: 'Entry', price: zoneMid(o.entryZone), cls: 'stroke-accent', text: 'fill-accent' },
    { key: 'SL', label: 'Stop', price: zoneMid(o.stopLossZone), cls: 'stroke-down', text: 'fill-down' },
  ];
  const values = [...candles.flatMap((c) => [c.high, c.low]), ...levels.map((l) => l.price), ...forecast.map((f) => f.value)];
  const pad = (Math.max(...values) - Math.min(...values)) * 0.08;
  const lo = Math.min(...values) - pad;
  const hi = Math.max(...values) + pad;
  const plotW = W - AXIS;
  const x = (t: number) => ((t - first.time) / (tEnd - first.time)) * plotW;
  const y = (v: number) => PAD_T + (1 - (v - lo) / (hi - lo)) * (H - PAD_T - PAD_B);
  const nowX = x(last.time);
  const bodyW = Math.max(2, (plotW / ((tEnd - first.time) / step)) * 0.62);
  const line = candles.map((c, i) => `${i ? 'L' : 'M'}${x(c.time).toFixed(1)} ${y(c.close).toFixed(1)}`).join(' ');
  const area = `${line} L${nowX.toFixed(1)} ${H - PAD_B} L${x(first.time).toFixed(1)} ${H - PAD_B} Z`;
  const proj = forecast.length ? `M${nowX.toFixed(1)} ${y(last.close).toFixed(1)} ${forecast.map((f) => `L${x(f.time).toFixed(1)} ${y(f.value).toFixed(1)}`).join(' ')}` : '';
  const signalX = Math.max(0, x(o.signalCandleTime));
  // Level labels take two lines (~28px): push them apart so they never overlap.
  const labelY = new Map<string, number>();
  [...levels]
    .sort((a, b) => y(a.price) - y(b.price))
    .reduce((prev, l) => {
      const ly = Math.max(y(l.price), prev + 28);
      labelY.set(l.key, ly);
      return ly;
    }, -Infinity);

  const pivots = swingPoints(candles);
  const ticks = [0.12, 0.42, 0.72].map((f) => candles[Math.round(f * (candles.length - 1))]).filter((c): c is Candle => !!c);
  const scanned = scan && scanAt >= 0 ? candles[scanAt] : undefined;
  const lineAt = startAt + 600;
  const lineDur = 1300;

  const intro = mode === 'intro';
  const on = (layer: ChartLayer) => visible.includes(layer);
  /** Timed (intro) or toggled (steps) behaviour for one layer. */
  const layer = (name: ChartLayer, at: number, extra?: string): { className?: string; style?: CSSProperties; 'data-layer'?: string; 'data-on'?: boolean } =>
    intro ? { className: extra ?? 'm-fade', style: { '--at': `${startAt + at}ms` } as CSSProperties } : { 'data-layer': 'fade', 'data-on': on(name) };
  const nowLayer = layer('now', 1900);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className={cn('h-auto w-full overflow-visible', className)}>
      <defs>
        <linearGradient id={`area-${gid}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Grid and time axis: the frame is laid down first. */}
      {[0.2, 0.45, 0.7, 0.95].map((f, i) => (
        <line
          key={f}
          x1="0"
          x2={plotW}
          y1={PAD_T + f * (H - PAD_T - PAD_B)}
          y2={PAD_T + f * (H - PAD_T - PAD_B)}
          className={cn('stroke-line', intro && 'm-grow-x')}
          strokeWidth="1"
          style={intro ? ({ '--at': `${startAt + i * 70}ms` } as CSSProperties) : undefined}
        />
      ))}
      <g className={intro ? 'm-fade' : undefined} style={intro ? ({ '--at': `${startAt + 320}ms` } as CSSProperties) : undefined}>
        {ticks.map((c) => (
          <text key={c.time} x={x(c.time)} y={H - 8} textAnchor="middle" fontSize="11" className="num fill-fg-3">
            {formatDateTime(c.time * 1000, 'UTC').replace(',', '')}
          </text>
        ))}
      </g>

      {/* Future region — exists only once NOW is drawn. */}
      <rect
        x={nowX}
        y={PAD_T - 12}
        width={plotW - nowX}
        height={H - PAD_T - PAD_B + 12}
        {...nowLayer}
        style={{ fill: 'var(--chart-forecast-region)', ...nowLayer.style }}
      />

      {/* Observed history */}
      {variant === 'line' ? (
        <g {...(intro ? {} : { 'data-layer': 'fade', 'data-on': on('history') })}>
          <path d={area} fill={`url(#area-${gid})`} className={intro ? 'm-fade' : undefined} style={intro ? ({ '--at': `${startAt + 1100}ms` } as CSSProperties) : undefined} />
          <path
            d={line}
            fill="none"
            pathLength={1}
            className={cn('stroke-accent', intro && 'm-draw')}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            style={intro ? ({ '--at': `${lineAt}ms`, '--dur': `${lineDur}ms`, '--len': 1 } as CSSProperties) : undefined}
          />
          {/* Swing points pop as the line reaches them. */}
          {pivots.map((i) => {
            const c = candles[i];
            if (!c) return null;
            return (
              <circle
                key={c.time}
                cx={x(c.time)}
                cy={y(c.close)}
                r="3"
                className={cn('fill-canvas stroke-accent', intro && 'm-pop')}
                strokeWidth="1.5"
                style={intro ? ({ '--at': `${Math.round(lineAt + (i / (candles.length - 1)) * lineDur * 0.9)}ms` } as CSSProperties) : undefined}
              />
            );
          })}
        </g>
      ) : (
        <g>
          {candles.map((c, i) => {
            const up = c.close >= c.open;
            const cx = x(c.time);
            return (
              <g
                key={c.time}
                className={cn(up ? 'fill-up stroke-up' : 'fill-down stroke-down', intro && 'm-fade')}
                {...(intro
                  ? { style: { '--at': `${startAt + 600 + i * 14}ms` } as CSSProperties }
                  : { 'data-layer': 'fade', 'data-on': on('history'), style: { '--layer-delay': `${i * 12}ms` } as CSSProperties })}
              >
                <line x1={cx} x2={cx} y1={y(c.high)} y2={y(c.low)} strokeWidth="1" />
                <rect x={cx - bodyW / 2} y={Math.min(y(c.open), y(c.close))} width={bodyW} height={Math.max(1.5, Math.abs(y(c.open) - y(c.close)))} rx="1" strokeWidth="0" />
              </g>
            );
          })}
        </g>
      )}

      {/* NOW boundary */}
      <g {...layer('now', 1900, 'm-fade')}>
        <line x1={nowX} x2={nowX} y1={PAD_T - 14} y2={H - PAD_B + 4} className="stroke-fg-3" strokeDasharray="3 4" strokeWidth="1" />
        <text x={nowX} y={H - 8} textAnchor="middle" fontSize="12" className="num fill-fg-3">
          NOW
        </text>
        {intro && <circle cx={nowX} cy={y(last.close)} r="4" className="now-pulse fill-none stroke-fg" strokeWidth="1" />}
        <circle cx={nowX} cy={y(last.close)} r="4" className="fill-fg" />
      </g>

      {/* Ambient crosshair over the observed history, with a labelled readout. */}
      {scanned && (
        <g aria-hidden className="m-fade">
          <g className="chart-scan" style={{ transform: `translate(${x(scanned.time).toFixed(1)}px, 0)` }}>
            <line x1="0" x2="0" y1={PAD_T - 6} y2={H - PAD_B} className="stroke-fg-3" strokeWidth="1" strokeDasharray="2 3" />
          </g>
          <g className="chart-scan" style={{ transform: `translate(0, ${y(scanned.close).toFixed(1)}px)` }}>
            <line x1="0" x2={plotW} y1="0" y2="0" className="stroke-fg-3" strokeWidth="1" strokeDasharray="2 3" opacity="0.6" />
          </g>
          <g className="chart-scan" style={{ transform: `translate(${x(scanned.time).toFixed(1)}px, ${y(scanned.close).toFixed(1)}px)` }}>
            <circle r="4.5" className="fill-canvas stroke-accent" strokeWidth="2" />
          </g>
          <text x="6" y="13" fontSize="11" className="num fill-fg-2">
            {formatDateTime(scanned.time * 1000, 'UTC').replace(',', '')} UTC · O {formatPrice(scanned.open, precision)} H {formatPrice(scanned.high, precision)} L{' '}
            {formatPrice(scanned.low, precision)} C {formatPrice(scanned.close, precision)} · simulated
          </text>
        </g>
      )}

      {/* Model levels (from the signal candle into the future) */}
      <g {...(intro ? {} : { 'data-layer': 'fade', 'data-on': on('levels') })}>
        {levels.map((l, i) => (
          <g key={l.key} className={intro ? 'm-fade' : undefined} style={intro ? ({ '--at': `${startAt + 2250 + i * 90}ms` } as CSSProperties) : undefined}>
            <line x1={signalX} x2={plotW} y1={y(l.price)} y2={y(l.price)} className={l.cls} strokeDasharray="5 5" strokeWidth="1.2" />
            <text x={plotW + 8} y={(labelY.get(l.key) ?? y(l.price)) - 3} fontSize="12" className={cn('num', l.text)}>
              {l.key}
            </text>
            <text x={plotW + 8} y={(labelY.get(l.key) ?? y(l.price)) + 11} fontSize="12" className="num fill-fg-3">
              {formatPrice(l.price, precision)}
            </text>
          </g>
        ))}
      </g>

      {/* Model projection — only supplied points, dashed violet, right of NOW */}
      {proj && (
        <g {...(intro ? {} : { 'data-layer': 'fade', 'data-on': on('projection') })}>
          <path
            d={proj}
            fill="none"
            pathLength={1}
            className={cn('stroke-forecast', intro && 'm-fade')}
            strokeWidth="2"
            strokeDasharray="0.03 0.025"
            strokeLinecap="round"
            style={intro ? ({ '--at': `${startAt + 2500}ms` } as CSSProperties) : undefined}
          />
          {forecast.map((f, i) => (
            <circle
              key={f.time}
              cx={x(f.time)}
              cy={y(f.value)}
              r="3"
              className={cn('fill-forecast', intro && 'm-pop')}
              style={intro ? ({ '--at': `${startAt + 2550 + i * 110}ms` } as CSSProperties) : undefined}
            />
          ))}
        </g>
      )}
    </svg>
  );
}
