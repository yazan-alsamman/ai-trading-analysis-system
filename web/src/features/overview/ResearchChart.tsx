import { useId } from 'react';
import type { Candle } from '@/domain/market';
import { timeframeSeconds, type Timeframe } from '@/domain/market';
import { zoneMid, type Opportunity } from '@/domain/opportunity';
import { formatPrice } from '@/lib/format';

interface Props {
  candles: readonly Candle[];
  timeframe: Timeframe;
  opportunity: Opportunity | null;
  precision: number;
  /** Accessible summary of what the chart shows (the SVG itself is decorative). */
  summary: string;
}

const W = 640;
const H = 260;
const PAD_T = 18;
const PAD_B = 22;
const AXIS_W = 64;

/**
 * Observed closes (solid), a NOW boundary, the model's levels, and its
 * projected path — ONLY when the model supplied one, and never beyond the
 * supplied points. Uses the same data as the workspace chart.
 */
export function ResearchChart({ candles, timeframe, opportunity, precision, summary }: Props) {
  const gradId = useId();
  const last = candles[candles.length - 1];
  if (!last || candles.length < 2) return null;

  const detected = opportunity?.status === 'detected' ? opportunity : null;
  const forecast = detected?.forecast?.filter((f) => f.time > last.time) ?? [];
  const step = timeframeSeconds(timeframe);
  // Future region: the model horizon when there is a setup, otherwise a short margin.
  const horizonEnd = detected ? Math.max(last.time + detected.horizonCandles * step, forecast[forecast.length - 1]?.time ?? 0) : last.time + 6 * step;
  const t0 = candles[0]?.time ?? last.time;
  const t1 = horizonEnd;

  const levels = detected
    ? [
        { key: 'TP', price: zoneMid(detected.takeProfitZone), cls: 'stroke-up', text: 'fill-up' },
        { key: 'Entry', price: zoneMid(detected.entryZone), cls: 'stroke-accent', text: 'fill-accent' },
        { key: 'SL', price: zoneMid(detected.stopLossZone), cls: 'stroke-down', text: 'fill-down' },
      ]
    : [];
  const values = [...candles.map((c) => c.close), ...levels.map((l) => l.price), ...forecast.map((f) => f.value)];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const padY = (hi - lo) * 0.08 || 1;
  lo -= padY;
  hi += padY;

  const plotW = W - AXIS_W;
  const x = (t: number) => ((t - t0) / (t1 - t0)) * plotW;
  const y = (v: number) => PAD_T + (1 - (v - lo) / (hi - lo)) * (H - PAD_T - PAD_B);
  const nowX = x(last.time);
  const line = candles.map((c, i) => `${i ? 'L' : 'M'}${x(c.time).toFixed(1)} ${y(c.close).toFixed(1)}`).join(' ');
  const area = `${line} L${nowX.toFixed(1)} ${H - PAD_B} L${x(t0).toFixed(1)} ${H - PAD_B} Z`;
  const fc = forecast.length ? `M${nowX.toFixed(1)} ${y(last.close).toFixed(1)} ` + forecast.map((f) => `L${x(f.time).toFixed(1)} ${y(f.value).toFixed(1)}`).join(' ') : '';
  const signalX = detected ? Math.max(0, x(detected.signalCandleTime)) : nowX;

  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" aria-hidden>
        <defs>
          <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--fg-primary)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="var(--fg-primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* horizontal guides */}
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1="0" x2={plotW} y1={PAD_T + f * (H - PAD_T - PAD_B)} y2={PAD_T + f * (H - PAD_T - PAD_B)} className="stroke-line" strokeWidth="1" />
        ))}
        {/* future region */}
        <rect x={nowX} y={PAD_T - 8} width={plotW - nowX} height={H - PAD_T - PAD_B + 8} style={{ fill: 'var(--chart-forecast-region)' }} />
        {/* observed */}
        <path d={area} fill={`url(#${gradId})`} />
        <path d={line} fill="none" className="stroke-fg" strokeWidth="1.6" strokeLinejoin="round" />
        {/* model levels, from the signal candle into the horizon */}
        {levels.map((l) => (
          <g key={l.key}>
            <line x1={signalX} x2={plotW} y1={y(l.price)} y2={y(l.price)} className={l.cls} strokeWidth="1" strokeDasharray="4 4" />
            <text x={plotW + 6} y={y(l.price) + 4} className={`${l.text} num`} fontSize="12">
              {l.key}
            </text>
          </g>
        ))}
        {/* projection — only the supplied points */}
        {fc && (
          <>
            <path d={fc} fill="none" className="stroke-forecast" strokeWidth="1.8" strokeDasharray="5 4" />
            {forecast.map((f) => (
              <circle key={f.time} cx={x(f.time)} cy={y(f.value)} r="2.2" className="fill-forecast" />
            ))}
          </>
        )}
        {/* NOW boundary */}
        <line x1={nowX} x2={nowX} y1={PAD_T - 10} y2={H - PAD_B} className="stroke-fg-3" strokeDasharray="2 3" strokeWidth="1" />
        <text x={nowX - 4} y={H - 6} textAnchor="end" className="fill-fg-3 num" fontSize="12">
          NOW
        </text>
        <circle cx={nowX} cy={y(last.close)} r="3.5" className="fill-fg" />
        <circle cx={nowX} cy={y(last.close)} r="7" className="fill-fg" opacity="0.15" />
        {/* last price label */}
        {!levels.length && (
          <text x={plotW + 6} y={y(last.close) + 4} className="fill-fg num" fontSize="12">
            {formatPrice(last.close, precision)}
          </text>
        )}
      </svg>
      <figcaption className="sr-only">{summary}</figcaption>
    </figure>
  );
}
