import { Search } from 'lucide-react';
import { useState } from 'react';
import { ChangeText } from '@/components/ui/Market';
import { Sparkline } from '@/components/ui/MiniCharts';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { INSTRUMENTS, matchesInstrument, type InstrumentSymbol } from '@/domain/instruments';
import type { Timeframe } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import type { LiveQuotes } from '@/hooks/useMarketData';
import { cn } from '@/lib/cn';
import { formatPercent, formatPercentChange, formatPrice } from '@/lib/format';

interface Props {
  quotes: LiveQuotes;
  active: InstrumentSymbol;
  onSelect: (symbol: InstrumentSymbol) => void;
  /** Recent closes per instrument for the sparkline (last value follows the live quote). */
  sparks: Map<InstrumentSymbol, number[]>;
  /** Latest AI analysis per instrument on the active timeframe. */
  signals: Map<InstrumentSymbol, Opportunity>;
  timeframe: Timeframe;
}

function AiTag({ o }: { o: Opportunity | undefined }) {
  if (!o) return <span className="text-xs text-fg-3">—</span>;
  if (o.status !== 'detected') return <span className="text-xs text-fg-3">No signal</span>;
  return (
    <span className="num inline-flex items-center gap-1 text-xs">
      <span className={o.direction === 'long' ? 'text-up' : 'text-down'}>{o.direction === 'long' ? 'Long' : 'Short'}</span>
      <span className="text-forecast">{formatPercent(o.probability)}</span>
    </span>
  );
}

/**
 * Watchlist: price, 24h change and shape, plus the AI status per pair, so the
 * list helps decide which instrument to open. Arrow keys move between rows.
 */
export function Watchlist({ quotes, active, onSelect, sparks, signals, timeframe }: Props) {
  const [query, setQuery] = useState('');
  const visible = INSTRUMENTS.filter((i) => matchesInstrument(i, query));

  const onKeyDown = (e: React.KeyboardEvent<HTMLUListElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const buttons = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('button[data-symbol]'));
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = buttons[Math.max(0, Math.min(buttons.length - 1, index + (e.key === 'ArrowDown' ? 1 : -1)))];
    if (next) {
      e.preventDefault();
      next.focus();
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="p-2">
        <label className="relative block">
          <span className="sr-only">Filter instruments</span>
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-fg-3" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter instruments"
            className="h-8 w-full rounded-md border border-line bg-inset pr-2 pl-8 text-sm text-fg placeholder:text-fg-3 hover:border-line-strong focus-visible:border-accent focus-visible:outline-none"
          />
        </label>
      </div>

      <div className="flex items-center justify-between px-3.5 pb-1 text-xs text-fg-3">
        <span>Pair · AI {timeframe}</span>
        <span>24h</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-2">
        {quotes.status === 'loading' ? (
          <Loading label="Loading quotes">
            <SkeletonRows rows={8} className="px-1.5" />
          </Loading>
        ) : quotes.status === 'error' && quotes.quotes.size === 0 ? (
          <ErrorState error={quotes.error} onRetry={quotes.reload} title="Quotes unavailable" compact />
        ) : visible.length === 0 ? (
          <EmptyState title="No matching instruments" description={`Nothing matches “${query}”.`} compact />
        ) : (
          <ul aria-label="Watchlist" onKeyDown={onKeyDown} className="flex flex-col">
            {visible.map((inst) => {
              const q = quotes.quotes.get(inst.symbol);
              const change = q ? (q.price - q.reference) / q.reference : null;
              const isActive = inst.symbol === active;
              const spark = sparks.get(inst.symbol);
              const values = spark && q ? [...spark.slice(0, -1), q.price] : (spark ?? []);
              return (
                <li key={inst.symbol}>
                  <button
                    type="button"
                    data-symbol={inst.symbol}
                    aria-current={isActive ? 'true' : undefined}
                    onClick={() => onSelect(inst.symbol)}
                    className={cn(
                      'relative grid w-full grid-cols-[1fr_auto_auto] items-center gap-x-2.5 rounded-md px-2 py-1.5 text-left transition-colors duration-150',
                      isActive ? 'bg-selected' : 'hover:bg-hover',
                    )}
                  >
                    {isActive && <span aria-hidden className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-accent" />}
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-fg">{inst.display}</span>
                      <AiTag o={signals.get(inst.symbol)} />
                    </span>
                    <Sparkline values={values} width={48} height={22} />
                    <span className="flex w-[78px] flex-col items-end">
                      <span className="num text-sm text-fg">{formatPrice(q?.price, inst.pricePrecision)}</span>
                      <ChangeText value={change} text={formatPercentChange(change)} className="text-xs" showIcon={false} />
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
