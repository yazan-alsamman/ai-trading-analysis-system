import { cn } from '@/lib/cn';

/**
 * Inline sparkline for scanning intraday shape. Decorative: the same
 * information is available as text (change %), so it is hidden from AT.
 * Colour follows market direction over the window.
 */
export function Sparkline({ values, width = 56, height = 20, className }: { values: readonly number[]; width?: number; height?: number; className?: string }) {
  if (values.length < 2) return <span aria-hidden style={{ width, height }} className={cn('inline-block', className)} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 1 - ((v - min) / span) * (height - 2)).toFixed(1)}`).join(' ');
  const first = values[0] ?? 0;
  const last = values[values.length - 1] ?? 0;
  const trend = last > first ? 'stroke-up' : last < first ? 'stroke-down' : 'stroke-fg-3';
  return (
    <svg aria-hidden width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cn('shrink-0 overflow-visible', className)}>
      <polyline points={points} fill="none" className={trend} strokeWidth={1.25} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Where the current price sits inside its 24h range.
 * Neutral colours: position in a range is not a direction.
 */
export function RangeBar({ low, high, value, className, label }: { low: number; high: number; value: number; className?: string; label: string }) {
  const pct = high > low ? Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100)) : 50;
  return (
    <div className={cn('relative h-1 rounded-full bg-hover', className)} role="img" aria-label={label}>
      <div className="absolute inset-y-0 left-0 rounded-full bg-line-strong" style={{ width: `${pct}%` }} />
      <div className="absolute top-1/2 h-2.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg" style={{ left: `${pct}%` }} />
    </div>
  );
}
