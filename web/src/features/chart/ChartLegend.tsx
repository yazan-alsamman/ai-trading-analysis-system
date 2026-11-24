import { DemoBadge } from '@/components/ui/Badge';
import { SourceTag } from '@/components/ui/SourceTag';
import type { IndicatorId } from '@/domain/indicators';
import type { Instrument } from '@/domain/instruments';
import type { Candle, Provenance, Timeframe, VolumeKind } from '@/domain/market';
import { cn } from '@/lib/cn';
import { formatCompact, formatDateTime, formatNumber, formatPercentChange, formatPrice, timeZoneLabel, trendOf } from '@/lib/format';
import type { IndicatorData } from './chartData';
import type { ChartPalette } from './chartTheme';

export interface HoverInfo {
  time: number;
  candle: Candle | undefined;
  values: Partial<Record<keyof IndicatorData | 'volume', number>>;
  forecastValue: number | undefined;
}

interface Props {
  instrument: Instrument;
  timeframe: Timeframe;
  candles: Candle[];
  hover: HoverInfo | null;
  indicatorData: IndicatorData;
  indicators: IndicatorId[];
  palette: ChartPalette | null;
  volumeKind: VolumeKind;
  provenance: Provenance;
  timeZone: string;
  hasForecast: boolean;
}

function lastValue(points: IndicatorData[keyof IndicatorData]): number | undefined {
  const p = points?.[points.length - 1];
  return p && 'value' in p ? p.value : undefined;
}

/**
 * TradingView-style legend: shows OHLC for the hovered bar (or the latest bar),
 * indicator values, and — in the forecast region — the predicted value,
 * explicitly labelled so it cannot be read as an observed price.
 */
export function ChartLegend({ instrument, timeframe, candles, hover, indicatorData, indicators, palette, volumeKind, provenance, timeZone, hasForecast }: Props) {
  const p = instrument.pricePrecision;
  const latest = candles[candles.length - 1];
  const inForecast = hover !== null && hover.candle === undefined && hover.forecastValue !== undefined;
  const candle = hover ? hover.candle : latest;
  const prev = candle ? candles[candles.indexOf(candle) - 1] : undefined;
  const change = candle && prev ? (candle.close - prev.close) / prev.close : null;
  const trend = trendOf(change);
  const valueOf = (key: keyof IndicatorData) => (hover ? hover.values[key] : lastValue(indicatorData[key]));

  const items: { key: string; label: string; color: string | undefined; value: string }[] = [];
  if (indicators.includes('sma20')) items.push({ key: 'sma20', label: 'SMA 20', color: palette?.ind1, value: formatPrice(valueOf('sma20'), p) });
  if (indicators.includes('ema50')) items.push({ key: 'ema50', label: 'EMA 50', color: palette?.ind2, value: formatPrice(valueOf('ema50'), p) });
  if (indicators.includes('bb20'))
    items.push({
      key: 'bb20',
      label: 'BB 20,2',
      color: palette?.ind3,
      value: `${formatPrice(valueOf('bbUpper'), p)} / ${formatPrice(valueOf('bbLower'), p)}`,
    });
  if (indicators.includes('rsi14')) items.push({ key: 'rsi14', label: 'RSI 14', color: palette?.ind1, value: formatNumber(valueOf('rsi14'), 1) });

  return (
    <div aria-hidden className="pointer-events-none absolute top-2 left-3 z-10 flex max-w-[calc(100%-200px)] sm:max-w-[calc(100%-180px)] flex-col gap-1 text-xs">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold text-fg">{instrument.display}</span>
        <span className="text-fg-3">{timeframe}</span>
        {provenance === 'demo' && <DemoBadge />}
        {provenance === 'live' && <SourceTag kind="live" />}
        {hover && <span className="num text-fg-3">{formatDateTime(hover.time * 1000, timeZone)} {timeZoneLabel(timeZone)}</span>}
      </div>

      {inForecast ? (
        <div className="flex flex-wrap items-center gap-x-2 rounded-sm bg-forecast-soft px-1.5 py-0.5 font-medium text-forecast">
          <span>AI forecast{provenance === 'demo' ? ' (simulated)' : ''} — not an observed price</span>
          <span className="num">{formatPrice(hover.forecastValue, p)}</span>
        </div>
      ) : candle ? (
        <div className="num flex flex-wrap gap-x-2.5 text-fg-2">
          <span>
            O <span className="text-fg">{formatPrice(candle.open, p)}</span>
          </span>
          <span>
            H <span className="text-fg">{formatPrice(candle.high, p)}</span>
          </span>
          <span>
            L <span className="text-fg">{formatPrice(candle.low, p)}</span>
          </span>
          <span>
            C <span className={cn(trend === 'up' ? 'text-up' : trend === 'down' ? 'text-down' : 'text-fg')}>{formatPrice(candle.close, p)}</span>
          </span>
          <span className={cn(trend === 'up' ? 'text-up' : trend === 'down' ? 'text-down' : 'text-fg-2')}>{formatPercentChange(change)}</span>
          {indicators.includes('volume') && (
            <span>
              {volumeKind === 'tick' ? 'Tick vol' : 'Vol'} <span className="text-fg">{formatCompact(candle.volume)}</span>
            </span>
          )}
        </div>
      ) : null}

      {items.length > 0 && (
        <div className="hidden flex-wrap gap-x-3 gap-y-0.5 sm:flex">
          {items.map((it) => (
            <span key={it.key} className="inline-flex items-center gap-1 text-fg-2">
              <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: it.color }} />
              {it.label}
              <span className="num text-fg">{it.value}</span>
            </span>
          ))}
        </div>
      )}

      {hasForecast && !inForecast && (
        <div className="hidden items-center gap-1.5 text-fg-3 sm:flex">
          <span className="inline-block w-4 border-t-2 border-dashed border-forecast" />
          <span>Dashed violet = AI forecast{provenance === 'demo' ? ' (simulated)' : ''}, right of “NOW”</span>
        </div>
      )}
    </div>
  );
}
