import type { Instrument } from '@/domain/instruments';
import { zoneMid, type Opportunity } from '@/domain/opportunity';
import { cn } from '@/lib/cn';
import { formatPips, formatPrice } from '@/lib/format';

/**
 * Risk → reward ladder drawn to scale: stop-loss on the left, take-profit on
 * the right (for longs and shorts alike), the entry zone in between, and a
 * marker for the current price. Answers "where is price now relative to my
 * plan?" at a glance.
 */
export function PriceLadder({ opportunity, instrument, currentPrice }: { opportunity: Opportunity; instrument: Instrument; currentPrice: number | undefined }) {
  const p = instrument.pricePrecision;
  const sl = zoneMid(opportunity.stopLossZone);
  const tp = zoneMid(opportunity.takeProfitZone);
  const span = tp - sl; // negative for shorts — the maths below works in "SL→TP" space
  const pos = (price: number) => Math.min(100, Math.max(0, ((price - sl) / span) * 100));
  const entryA = pos(opportunity.entryZone.low);
  const entryB = pos(opportunity.entryZone.high);
  const now = currentPrice === undefined ? null : pos(currentPrice);
  const beyond = currentPrice !== undefined && (((currentPrice - sl) / span) * 100 < 0 || ((currentPrice - sl) / span) * 100 > 100);

  const label =
    currentPrice === undefined
      ? 'Current price unavailable'
      : `Current price ${formatPrice(currentPrice, p)}: ${formatPips(currentPrice - sl, instrument.pipSize)} from stop-loss, ${formatPips(tp - currentPrice, instrument.pipSize)} to take-profit`;

  return (
    <figure className="flex flex-col gap-2">
      <div className="relative h-8" role="img" aria-label={label}>
        {/* risk side and reward side */}
        <div className="absolute top-3.5 right-0 left-0 h-1 overflow-hidden rounded-full bg-hover">
          <div className="absolute inset-y-0 left-0 bg-down/45" style={{ width: `${Math.min(entryA, entryB)}%` }} />
          <div className="absolute inset-y-0 right-0 bg-up/45" style={{ width: `${100 - Math.max(entryA, entryB)}%` }} />
        </div>
        <div
          className="absolute top-2.5 h-3 rounded-sm border border-accent bg-accent-soft"
          style={{ left: `${Math.min(entryA, entryB)}%`, width: `${Math.max(1.5, Math.abs(entryB - entryA))}%` }}
        />
        {now !== null && (
          <div className="absolute top-0 flex -translate-x-1/2 flex-col items-center" style={{ left: `${now}%` }}>
            <span className={cn('h-8 w-0.5 rounded-full', beyond ? 'bg-warning' : 'bg-fg')} />
          </div>
        )}
      </div>
      <figcaption className="num grid grid-cols-3 text-xs">
        <span className="text-left">
          <span className="block text-fg-3">Stop-loss</span>
          <span className="text-down">{formatPrice(sl, p)}</span>
        </span>
        <span className="text-center">
          <span className="block text-fg-3">Now</span>
          <span className={beyond ? 'text-warning' : 'text-fg'}>{formatPrice(currentPrice, p)}</span>
        </span>
        <span className="text-right">
          <span className="block text-fg-3">Take-profit</span>
          <span className="text-up">{formatPrice(tp, p)}</span>
        </span>
      </figcaption>
      {beyond && <p className="text-xs text-warning">Price has moved outside the stop-loss / take-profit range of this analysis.</p>}
    </figure>
  );
}
