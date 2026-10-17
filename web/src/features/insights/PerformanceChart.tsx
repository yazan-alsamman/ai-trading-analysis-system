import { useId, useMemo } from 'react';
import type { PredictionRecord } from '@/domain/predictions';
import { formatDate, formatR } from '@/lib/format';

const W = 600;
const H = 200;

/**
 * Cumulative realised result (in R) of resolved predictions over time.
 * The line is stretched to the container (preserveAspectRatio="none"); labels
 * are HTML so text stays crisp and at the 12px minimum at any width.
 * Green above zero / red below = profit vs loss, the only use of those colours.
 */
export function PerformanceChart({ records, timeZone }: { records: readonly PredictionRecord[]; timeZone: string }) {
  const clipUp = useId();
  const clipDown = useId();
  const points = useMemo(() => {
    let total = 0;
    return records
      .filter((r) => r.outcome !== 'open' && r.realizedR !== undefined && r.resolvedAt !== undefined)
      .sort((a, b) => (a.resolvedAt ?? 0) - (b.resolvedAt ?? 0))
      .map((r) => {
        total += r.realizedR ?? 0;
        return { t: r.resolvedAt ?? 0, v: total };
      });
  }, [records]);

  if (points.length < 2) return <p className="py-10 text-center text-sm text-fg-3">Not enough resolved predictions to plot.</p>;

  const values = points.map((p) => p.v);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const pad = (hi - lo) * 0.08 || 1;
  const yMin = lo - pad;
  const yMax = hi + pad;
  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - ((v - yMin) / (yMax - yMin)) * H;
  const zeroY = y(0);
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
  const area = `${line} L${W},${zeroY.toFixed(1)} L0,${zeroY.toFixed(1)} Z`;
  const last = points[points.length - 1];
  const first = points[0];
  const pct = (v: number) => `${(y(v) / H) * 100}%`;

  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-fg-3">
        <span>
          Cumulative result over {points.length} resolved predictions
        </span>
        <span className="num text-sm">
          Total{' '}
          <span className={last && last.v >= 0 ? 'text-up' : 'text-down'}>{formatR(last?.v)}</span>
        </span>
      </figcaption>
      <div className="relative h-52 pl-12">
        {[yMax - pad, 0, yMin + pad].filter((v, i, a) => a.indexOf(v) === i).map((v) => (
          <span key={v} className="num absolute left-0 w-10 -translate-y-1/2 text-right text-xs text-fg-3" style={{ top: pct(v) }}>
            {formatR(v, 1)}
          </span>
        ))}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Cumulative result ${formatR(last?.v)} from ${formatDate(first?.t, timeZone)} to ${formatDate(last?.t, timeZone)}`}
          className="h-full w-full overflow-visible"
        >
          <defs>
            <clipPath id={clipUp}>
              <rect x="0" y="0" width={W} height={zeroY} />
            </clipPath>
            <clipPath id={clipDown}>
              <rect x="0" y={zeroY} width={W} height={H - zeroY} />
            </clipPath>
          </defs>
          <line x1="0" x2={W} y1={zeroY} y2={zeroY} className="stroke-line-strong" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
          <path d={area} className="fill-up-soft" clipPath={`url(#${clipUp})`} />
          <path d={area} className="fill-down-soft" clipPath={`url(#${clipDown})`} />
          <path d={line} fill="none" className="stroke-fg-2" strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="num flex justify-between pl-12 text-xs text-fg-3">
        <span>{formatDate(first?.t, timeZone)}</span>
        <span>{formatDate(last?.t, timeZone)}</span>
      </div>
    </figure>
  );
}
