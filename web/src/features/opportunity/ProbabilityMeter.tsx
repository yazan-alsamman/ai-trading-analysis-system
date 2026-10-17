import { cn } from '@/lib/cn';
import { formatPercent, formatProbabilityBand } from '@/lib/format';

interface Props {
  probability: number;
  band?: { low: number; high: number } | undefined;
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Probability with its confidence band. Uses the forecast (AI output) colour —
 * never green/red — because a probability is not a price movement.
 * A tick marks 50% so "better than a coin flip" is visible at a glance.
 */
export function ProbabilityMeter({ probability, band, size = 'md', className }: Props) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, v * 100))}%`;
  const label = `Probability ${formatPercent(probability)}${band ? `, confidence band ${formatProbabilityBand(band)}` : ''}`;
  return (
    <div className={cn('w-full', className)}>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(probability * 100)}
        aria-valuetext={label}
        className={cn('relative w-full overflow-hidden rounded-full bg-hover', size === 'sm' ? 'h-1.5' : 'h-2')}
      >
        <div className="absolute inset-y-0 left-0 bg-forecast/75" style={{ width: pct(probability) }} />
        {band && (
          <div
            className="absolute inset-y-0 border-x-2 border-forecast bg-forecast/30"
            style={{ left: pct(band.low), width: pct(band.high - band.low) }}
          />
        )}
        <div aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-fg-3/70" />
      </div>
      {size === 'md' && (
        <div aria-hidden className="mt-1 flex justify-between text-xs text-fg-3">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      )}
    </div>
  );
}
