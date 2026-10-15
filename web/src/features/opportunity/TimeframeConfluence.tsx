import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { TIMEFRAMES, type Timeframe } from '@/domain/market';
import { confluenceSummary, type Opportunity } from '@/domain/opportunity';
import { cn } from '@/lib/cn';
import { formatPercent } from '@/lib/format';

const ROLE: Record<Timeframe, string> = { '15m': 'Detection', '1h': 'Confirmation', '4h': 'Regime' };

/**
 * Multi-timeframe view from the Feature 12 spec: 15m detects, 1h confirms,
 * 4h sets the regime. Each cell is a button that switches the chart.
 */
export function TimeframeConfluence({ items, active, onSelect }: { items: readonly Opportunity[]; active: Timeframe; onSelect: (tf: Timeframe) => void }) {
  const byTf = new Map(items.map((o) => [o.timeframe, o]));
  const { agree, direction } = confluenceSummary(items);
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-xs font-medium text-fg-2">Timeframe alignment</h3>
        <span className="text-xs text-fg-3">
          {direction ? `${agree} of 3 ${direction === 'long' ? 'long' : 'short'}` : 'No detections'}
        </span>
      </div>
      <div role="group" aria-label="Analysis per timeframe" className="grid grid-cols-3 gap-1.5">
        {TIMEFRAMES.map(({ id }) => {
          const o = byTf.get(id);
          const detected = o?.status === 'detected';
          const Icon = !detected ? Minus : o.direction === 'long' ? ArrowUpRight : ArrowDownRight;
          return (
            <button
              key={id}
              type="button"
              aria-pressed={id === active}
              onClick={() => onSelect(id)}
              className={cn(
                'flex flex-col items-start rounded-md border px-2 py-1.5 text-left transition-colors',
                id === active ? 'border-accent/60 bg-selected' : 'border-line hover:bg-hover',
              )}
            >
              <span className="flex w-full items-center justify-between text-xs">
                <span className="font-medium text-fg">{id}</span>
                <Icon aria-hidden className={cn('size-3.5', !detected ? 'text-fg-3' : o.direction === 'long' ? 'text-up' : 'text-down')} />
              </span>
              <span className="num text-sm text-fg">
                {detected ? (
                  <>
                    <span className={o.direction === 'long' ? 'text-up' : 'text-down'}>{o.direction === 'long' ? 'Long' : 'Short'}</span>{' '}
                    <span className="text-forecast">{formatPercent(o.probability)}</span>
                  </>
                ) : (
                  <span className="text-fg-3">{o ? 'None' : '—'}</span>
                )}
              </span>
              <span className="text-xs text-fg-3">{ROLE[id]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
