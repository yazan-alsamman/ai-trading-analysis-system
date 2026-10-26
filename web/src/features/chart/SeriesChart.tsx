import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
  type IChartApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useRef } from 'react';
import { usePreferences } from '@/app/contexts';
import type { Candle } from '@/domain/market';
import type { ChartMarker } from '@/domain/strategies';
import { cn } from '@/lib/cn';
import { formatDateTime } from '@/lib/format';
import { readChartPalette, type ChartPalette } from './chartTheme';

export interface SeriesLine {
  name: string;
  /** Unix seconds; `null` values (indicator warm-up) leave a gap. */
  points: readonly { time: number; value: number | null }[];
  /** Palette key or a CSS colour. */
  color?: keyof ChartPalette | string;
  /** 0 = main pane (with candles); 1+ = separate panes below. */
  pane?: number;
}

interface SeriesChartProps {
  /** Accessible description of what the chart shows (the canvas itself is not readable). */
  label: string;
  candles?: readonly Candle[];
  lines?: readonly SeriesLine[];
  /** Lightweight Charts markers as the backend sends them (time in unix seconds). */
  markers?: readonly ChartMarker[];
  height?: number;
  className?: string;
  /** Price precision for the right scale. */
  precision?: number;
}

const LINE_COLORS: (keyof ChartPalette)[] = ['accent', 'ind1', 'ind2', 'ind3', 'forecast'];
const NO_LINES: readonly SeriesLine[] = [];
const NO_MARKERS: readonly ChartMarker[] = [];

/**
 * A static chart of backend series: a strategy preview (candles + indicator
 * lines + signal markers) or a backtest's equity and drawdown curves. Unlike
 * the workspace PriceChart it has no live updates, overlays or drawing tools.
 * Pass memoised `candles`/`lines`/`markers`: the chart is rebuilt when they change.
 */
export function SeriesChart({ label, candles, lines = NO_LINES, markers = NO_MARKERS, height = 320, className, precision = 2 }: SeriesChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { resolvedTheme, timeZone } = usePreferences();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const palette = readChartPalette();
    const chart: IChartApi = createChart(el, {
      autoSize: true,
      layout: {
        attributionLogo: true, // Licence requirement (Apache-2.0 NOTICE) — keep enabled.
        background: { type: ColorType.Solid, color: palette.background },
        textColor: palette.text,
        fontFamily: "'Inter Variable', system-ui, sans-serif",
        fontSize: 11,
        panes: { separatorColor: palette.border, separatorHoverColor: palette.grid },
      },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      crosshair: {
        vertLine: { color: palette.crosshair, labelBackgroundColor: palette.crosshair, style: LineStyle.Dashed },
        horzLine: { color: palette.crosshair, labelBackgroundColor: palette.crosshair, style: LineStyle.Dashed },
      },
      rightPriceScale: { borderColor: palette.border },
      timeScale: { borderColor: palette.border, timeVisible: true, secondsVisible: false },
      localization: { locale: 'en-GB', timeFormatter: (time: Time) => formatDateTime((time as number) * 1000, timeZone) },
    });
    const priceFormat = { type: 'price' as const, precision, minMove: 1 / 10 ** precision };

    let markerHost = null as ReturnType<typeof chart.addSeries> | null;
    if (candles?.length) {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: palette.up,
        downColor: palette.down,
        borderVisible: false,
        wickUpColor: palette.up,
        wickDownColor: palette.down,
        priceFormat,
      });
      series.setData(candles.map((c) => ({ time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close })));
      markerHost = series;
    }
    lines.forEach((line, i) => {
      const key = line.color ?? LINE_COLORS[i % LINE_COLORS.length] ?? 'accent';
      const color = key in palette ? palette[key as keyof ChartPalette] : key;
      const series = chart.addSeries(LineSeries, { color, lineWidth: 2, priceLineVisible: false, title: line.name, priceFormat }, line.pane ?? 0);
      series.setData(
        [...line.points]
          .sort((a, b) => a.time - b.time)
          .filter((p, idx, arr) => idx === 0 || p.time !== arr[idx - 1]?.time)
          .map((p) => (p.value === null ? { time: p.time as UTCTimestamp } : { time: p.time as UTCTimestamp, value: p.value })),
      );
      markerHost ??= series;
    });
    if (markerHost && markers.length) {
      const sorted: SeriesMarker<Time>[] = [...markers]
        .sort((a, b) => a.time - b.time)
        .map((m) => ({ time: m.time as UTCTimestamp, position: m.position, shape: m.shape, color: m.color, text: m.text }));
      createSeriesMarkers(markerHost, sorted);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [candles, lines, markers, resolvedTheme, timeZone, precision]);

  return (
    <figure className={cn('m-0', className)}>
      <div ref={ref} role="img" aria-label={label} style={{ height }} className="w-full" />
      <figcaption className="sr-only">{label}</figcaption>
    </figure>
  );
}
