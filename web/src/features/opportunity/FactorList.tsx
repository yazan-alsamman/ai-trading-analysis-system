import type { ExplanationFactor } from '@/domain/opportunity';
import { cn } from '@/lib/cn';
import { formatNumber } from '@/lib/format';

/**
 * Explainable-AI factors (spec: top 5). Bars are centred: right = supports the
 * stated direction, left = opposes it. Words + signs carry the meaning; colour
 * is secondary and deliberately not green/red.
 */
export function FactorList({ factors, direction }: { factors: ExplanationFactor[]; direction: string }) {
  const max = Math.max(0.0001, ...factors.map((f) => Math.abs(f.contribution)));
  return (
    <ol className="flex flex-col gap-2.5">
      {factors.map((f) => {
        const supports = f.contribution >= 0;
        const width = `${(Math.abs(f.contribution) / max) * 50}%`;
        return (
          <li key={f.id} className="min-w-0">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-sm text-fg" title={f.label}>
                {f.label}
              </span>
              <span className={cn('num shrink-0 text-xs', supports ? 'text-accent' : 'text-fg-2')}>
                {supports ? '+' : '−'}
                {formatNumber(Math.abs(f.contribution), 2)}
              </span>
            </div>
            <div className="relative mt-1 h-1 rounded-full bg-hover" aria-hidden>
              <div className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
              <div
                className={cn('absolute inset-y-0 rounded-full', supports ? 'left-1/2 bg-accent' : 'right-1/2 bg-fg-3')}
                style={{ width }}
              />
            </div>
            <p className="mt-1 text-xs text-fg-3">
              <span className="sr-only">{supports ? `Supports ${direction}. ` : `Opposes ${direction}. `}</span>
              {f.detail}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
