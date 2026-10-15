import { ChangeText, FeedStatusPill } from '@/components/ui/Market';
import { RangeBar } from '@/components/ui/MiniCharts';
import { Skeleton } from '@/components/ui/StateViews';
import type { Instrument } from '@/domain/instruments';
import type { Candle, FeedStatus, Provenance, Quote, Timeframe } from '@/domain/market';
import { confluenceSummary, type Opportunity } from '@/domain/opportunity';
import { sessionSummary } from '@/domain/sessions';
import { formatClock, formatPercent, formatPercentChange, formatPrice, formatPriceChange, formatRelative, timeZoneLabel } from '@/lib/format';
import { dayStats } from './dayStats';

interface Props {
  instrument: Instrument;
  candles: Candle[];
  /** Same quote the watchlist shows — keeps the 24h change identical in both places. */
  quote: Quote | undefined;
  feedStatus: FeedStatus;
  lastUpdateMs: number | undefined;
  provenance: Provenance | undefined;
  timeZone: string;
  now: number;
  loading: boolean;
  timeframe: Timeframe;
  opportunity: Opportunity | undefined;
  confluence: Opportunity[] | undefined;
}

function Divider() {
  return <span aria-hidden className="hidden h-8 w-px bg-line md:block" />;
}

/** Ticker strip: identity, price, 24h position, session, AI verdict and data freshness in one line. */
export function InstrumentHeader(props: Props) {
  const { instrument, candles, quote, feedStatus, lastUpdateMs, timeZone, now, loading, timeframe, opportunity, confluence } = props;
  const stats = dayStats(candles, quote);
  const p = instrument.pricePrecision;
  const agree = confluence ? confluenceSummary(confluence) : null;
  const detected = opportunity?.status === 'detected' ? opportunity : null;

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line bg-surface px-4 py-2">
      <div className="min-w-0">
        <h1 className="text-md leading-tight font-semibold text-fg">{instrument.display}</h1>
        <p className="truncate text-xs text-fg-3">{instrument.name}</p>
      </div>

      {loading || !stats ? (
        <div className="flex items-center gap-3" aria-hidden>
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-36" />
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2.5">
            <p className="num text-xl leading-none font-medium text-fg" aria-label={`Last price ${formatPrice(stats.price, p)}`}>
              {formatPrice(stats.price, p)}
            </p>
            <div className="flex flex-col items-start text-xs leading-tight">
              <ChangeText value={stats.change} text={formatPriceChange(stats.change, p)} />
              <ChangeText value={stats.change} text={`${formatPercentChange(stats.changeRatio)} 24h`} showIcon={false} />
            </div>
          </div>
          <Divider />
          <div className="hidden w-44 sm:block">
            <div className="num mb-1 flex justify-between gap-2 text-xs">
              <span className="text-fg-3">
                L <span className="text-fg-2">{formatPrice(stats.low, p)}</span>
              </span>
              <span className="text-fg-3">
                H <span className="text-fg-2">{formatPrice(stats.high, p)}</span>
              </span>
            </div>
            <RangeBar
              low={stats.low}
              high={stats.high}
              value={stats.price}
              label={`Price at ${formatPercent((stats.price - stats.low) / Math.max(stats.high - stats.low, 1e-12))} of its 24 hour range`}
            />
          </div>
          <Divider />
          <div className="hidden text-xs 2xl:block">
            <p className="text-fg-3">Session</p>
            <p className="text-fg-2">{sessionSummary(now).replace(/ session$/, '')}</p>
          </div>
          <div className="text-xs">
            <p className="text-fg-3">AI · {timeframe}</p>
            <p className="num">
              {detected ? (
                <>
                  <span className={detected.direction === 'long' ? 'text-up' : 'text-down'}>{detected.direction === 'long' ? 'Long' : 'Short'}</span>{' '}
                  <span className="text-forecast">{formatPercent(detected.probability)}</span>
                </>
              ) : (
                <span className="text-fg-2">{opportunity ? 'No signal' : '—'}</span>
              )}
              {agree?.direction && (
                <span className="ml-1.5 font-sans text-fg-3">
                  · {agree.agree}/3 timeframes {agree.direction}
                </span>
              )}
            </p>
          </div>
        </>
      )}

      <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1">
        <FeedStatusPill status={feedStatus} />
        <span className="num text-xs text-fg-3" title={lastUpdateMs ? `Last update ${formatRelative(lastUpdateMs, now)}` : undefined}>
          {formatClock(lastUpdateMs, timeZone)} {timeZoneLabel(timeZone)}
        </span>
      </div>
    </div>
  );
}
