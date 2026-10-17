import {
  AreaSeries,
  BarSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  TickMarkType,
  type AutoscaleInfo,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesType,
  type Time,
} from 'lightweight-charts';
import { Maximize2, ZoomIn, ZoomOut } from 'lucide-react';
import { memo, useEffect, useId, useMemo, useRef, useState } from 'react';
import { IconButton } from '@/components/ui/Button';
import type { IndicatorId } from '@/domain/indicators';
import type { Instrument } from '@/domain/instruments';
import { CHART_TYPES, type Candle, type ChartType, type Provenance, type Timeframe, type VolumeKind } from '@/domain/market';
import { zoneMid, type Opportunity } from '@/domain/opportunity';
import { formatClock, formatDate, formatDateTime, formatPercent, formatPrice, timeZoneLabel } from '@/lib/format';
import { computeIndicatorData, toMainPoint, toVolumePoint, ts, type IndicatorData } from './chartData';
import { ChartLegend, type HoverInfo } from './ChartLegend';
import { readChartPalette, type ChartPalette } from './chartTheme';
import { OpportunityOverlay } from './OpportunityOverlay';

const INITIAL_BARS = 120;
/** Empty logical bars kept right of the last candle — room for the forecast. */
const RIGHT_SPACE = 16;

type LineKey = Exclude<keyof IndicatorData, never>;
type IndicatorSeriesMap = Partial<Record<'volume' | LineKey, ISeriesApi<SeriesType>>>;

export interface PriceChartProps {
  instrument: Instrument;
  timeframe: Timeframe;
  candles: Candle[];
  chartType: ChartType;
  indicators: IndicatorId[];
  /** Detected opportunity to draw (zones + levels). */
  opportunity: Opportunity | null;
  showForecast: boolean;
  timeZone: string;
  theme: 'dark' | 'light';
  volumeKind: VolumeKind;
  provenance: Provenance;
}

/** Extract a numeric `value` from crosshair series data (line/histogram points). */
function numericValue(point: unknown): number | undefined {
  return point && typeof point === 'object' && 'value' in point && typeof point.value === 'number' ? point.value : undefined;
}

/** Binary search for a candle by open time. */
function findCandle(candles: readonly Candle[], time: number): Candle | undefined {
  let lo = 0;
  let hi = candles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const c = candles[mid];
    if (!c) return undefined;
    if (c.time === time) return c;
    if (c.time < time) lo = mid + 1;
    else hi = mid - 1;
  }
  return undefined;
}

function tickFormatter(timeZone: string) {
  return (time: Time, type: TickMarkType): string => {
    const ms = (time as number) * 1000;
    switch (type) {
      case TickMarkType.Year:
        return new Intl.DateTimeFormat('en-GB', { timeZone, year: 'numeric' }).format(ms);
      case TickMarkType.Month:
        return new Intl.DateTimeFormat('en-GB', { timeZone, month: 'short' }).format(ms);
      case TickMarkType.DayOfMonth:
        return new Intl.DateTimeFormat('en-GB', { timeZone, day: '2-digit', month: 'short' }).format(ms);
      case TickMarkType.TimeWithSeconds:
        return formatClock(ms, timeZone, true);
      default:
        return formatClock(ms, timeZone, false);
    }
  };
}

function PriceChartImpl(props: PriceChartProps) {
  const { instrument, timeframe, candles, chartType, indicators, opportunity, showForecast, timeZone, theme, volumeKind, provenance } = props;
  const precision = instrument.pricePrecision;

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<ISeriesApi<SeriesType> | null>(null);
  const seriesRef = useRef<IndicatorSeriesMap>({});
  const forecastRef = useRef<ISeriesApi<'Line'> | null>(null);
  const priceLinesRef = useRef<{ series: ISeriesApi<SeriesType>; lines: IPriceLine[] } | null>(null);
  const [overlay] = useState(() => new OpportunityOverlay());
  const extraRangeRef = useRef<{ min: number; max: number } | null>(null);
  const fullSyncRef = useRef(true);
  const syncedRef = useRef({ key: '', length: 0, rangeKey: '' });
  const candlesRef = useRef(candles);
  candlesRef.current = candles;

  const summaryId = useId();
  const [palette, setPalette] = useState<ChartPalette | null>(null);
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const indicatorKey = indicators.join(',');
  const indicatorData = useMemo(() => computeIndicatorData(candles, indicators), [candles, indicators]);

  /* -------------------------------------------------- create / destroy */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        attributionLogo: true, // Licence requirement (Apache-2.0 NOTICE) — keep enabled.
        fontFamily: "'Inter Variable', system-ui, sans-serif",
        fontSize: 11,
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 6, minBarSpacing: 1.5 },
      rightPriceScale: { scaleMargins: { top: 0.08, bottom: 0.08 } },
    });
    chartRef.current = chart;

    const onMove = (param: MouseEventParams<Time>) => {
      if (param.time === undefined || !param.point) {
        setHover(null);
        return;
      }
      const time = param.time as number;
      const values: HoverInfo['values'] = {};
      for (const [key, series] of Object.entries(seriesRef.current)) {
        const value = numericValue(series ? param.seriesData.get(series) : undefined);
        if (value !== undefined) values[key as keyof HoverInfo['values']] = value;
      }
      const forecastPoint = forecastRef.current ? param.seriesData.get(forecastRef.current) : undefined;
      setHover({
        time,
        candle: findCandle(candlesRef.current, time),
        values,
        forecastValue: numericValue(forecastPoint),
      });
    };
    chart.subscribeCrosshairMove(onMove);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
      chartRef.current = null;
      mainRef.current = null;
      seriesRef.current = {};
      forecastRef.current = null;
      priceLinesRef.current = null;
      fullSyncRef.current = true;
      syncedRef.current = { key: '', length: 0, rangeKey: '' };
    };
  }, []);

  /* ------------------------------------------------ theme → palette */
  useEffect(() => {
    // Wait one frame so the <html data-theme> attribute has been applied.
    const id = requestAnimationFrame(() => setPalette(readChartPalette()));
    return () => cancelAnimationFrame(id);
  }, [theme]);

  /* -------------------------------------------- chart-wide options */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !palette) return;
    chart.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: palette.background },
        textColor: palette.text,
        panes: { separatorColor: palette.border, separatorHoverColor: palette.grid },
      },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      crosshair: {
        vertLine: { color: palette.crosshair, labelBackgroundColor: palette.crosshair, style: LineStyle.Dashed },
        horzLine: { color: palette.crosshair, labelBackgroundColor: palette.crosshair, style: LineStyle.Dashed },
      },
      rightPriceScale: { borderColor: palette.border },
      timeScale: { borderColor: palette.border, tickMarkFormatter: tickFormatter(timeZone) },
      localization: {
        locale: 'en-GB',
        timeFormatter: (time: Time) => formatDateTime((time as number) * 1000, timeZone),
      },
    });
  }, [palette, timeZone]);

  /* ------------------------------------------------- main price series */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !palette) return;
    if (mainRef.current) {
      mainRef.current.detachPrimitive(overlay);
      chart.removeSeries(mainRef.current);
      priceLinesRef.current = null;
    }
    const priceFormat = { type: 'price' as const, precision, minMove: 10 ** -precision };
    const autoscaleInfoProvider = (original: () => AutoscaleInfo | null): AutoscaleInfo | null => {
      const res = original();
      const extra = extraRangeRef.current;
      if (!res?.priceRange || !extra) return res;
      return { ...res, priceRange: { minValue: Math.min(res.priceRange.minValue, extra.min), maxValue: Math.max(res.priceRange.maxValue, extra.max) } };
    };
    const common = { priceFormat, autoscaleInfoProvider, title: '' };

    let series: ISeriesApi<SeriesType>;
    if (chartType === 'candles') {
      series = chart.addSeries(CandlestickSeries, {
        ...common,
        upColor: palette.up,
        downColor: palette.down,
        borderUpColor: palette.up,
        borderDownColor: palette.down,
        wickUpColor: palette.up,
        wickDownColor: palette.down,
      });
    } else if (chartType === 'bars') {
      series = chart.addSeries(BarSeries, { ...common, upColor: palette.up, downColor: palette.down, thinBars: false });
    } else if (chartType === 'line') {
      series = chart.addSeries(LineSeries, { ...common, color: palette.price, lineWidth: 2, crosshairMarkerRadius: 3 });
    } else {
      series = chart.addSeries(AreaSeries, {
        ...common,
        lineColor: palette.price,
        topColor: palette.zoneEntry,
        bottomColor: 'rgba(0,0,0,0)',
        lineWidth: 2,
      });
    }
    series.attachPrimitive(overlay);
    mainRef.current = series;
    fullSyncRef.current = true;
  }, [chartType, palette, precision, overlay]);

  /* -------------------------------------------------- indicator series */
  useEffect(() => {
    const chart = chartRef.current;
    const main = mainRef.current;
    if (!chart || !palette || !main) return;

    for (const s of Object.values(seriesRef.current)) if (s) chart.removeSeries(s);
    seriesRef.current = {};
    while (chart.panes().length > 1) chart.removePane(chart.panes().length - 1);

    const line = (color: string, style: LineStyle = LineStyle.Solid) => ({
      color,
      lineWidth: 1 as const,
      lineStyle: style,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceFormat: { type: 'price' as const, precision, minMove: 10 ** -precision },
    });

    const hasVolume = indicators.includes('volume');
    if (hasVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        priceScaleId: 'volume',
        priceFormat: { type: 'volume' },
        priceLineVisible: false,
        lastValueVisible: false,
      });
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.86, bottom: 0 }, visible: false });
      volume.setSeriesOrder(0);
      seriesRef.current.volume = volume;
    }
    main.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: hasVolume ? 0.16 : 0.08 } });

    if (indicators.includes('sma20')) seriesRef.current.sma20 = chart.addSeries(LineSeries, line(palette.ind1));
    if (indicators.includes('ema50')) seriesRef.current.ema50 = chart.addSeries(LineSeries, line(palette.ind2));
    if (indicators.includes('bb20')) {
      seriesRef.current.bbUpper = chart.addSeries(LineSeries, line(palette.ind3));
      seriesRef.current.bbMiddle = chart.addSeries(LineSeries, line(palette.ind3, LineStyle.Dotted));
      seriesRef.current.bbLower = chart.addSeries(LineSeries, line(palette.ind3));
    }
    if (indicators.includes('rsi14')) {
      const rsi = chart.addSeries(
        LineSeries,
        { ...line(palette.ind1), lastValueVisible: true, priceFormat: { type: 'price', precision: 1, minMove: 0.1 } },
        1,
      );
      for (const level of [70, 30]) {
        rsi.createPriceLine({ price: level, color: palette.muted, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: '' });
      }
      chart.panes()[0]?.setStretchFactor(4);
      chart.panes()[1]?.setStretchFactor(1);
      seriesRef.current.rsi14 = rsi;
    }
    fullSyncRef.current = true;
    // `indicatorKey` captures the indicators array contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indicatorKey, palette, precision, chartType]);

  /* --------------------------------------------------------- data sync */
  useEffect(() => {
    const chart = chartRef.current;
    const main = mainRef.current;
    if (!chart || !main || !palette) return;
    const key = `${instrument.symbol}:${timeframe}`;
    const synced = syncedRef.current;
    const last = candles[candles.length - 1];
    const full = fullSyncRef.current || synced.key !== key || Math.abs(candles.length - synced.length) > 1 || !last;
    const s = seriesRef.current;
    const lineKeys: LineKey[] = ['sma20', 'ema50', 'bbUpper', 'bbMiddle', 'bbLower', 'rsi14'];

    if (full) {
      main.setData(candles.map((c) => toMainPoint(c, chartType)));
      s.volume?.setData(candles.map((c) => toVolumePoint(c, palette.volumeUp, palette.volumeDown)));
      for (const k of lineKeys) {
        const data = indicatorData[k];
        if (s[k] && data) s[k].setData(data);
      }
      if (synced.rangeKey !== key && candles.length > 0) {
        chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, candles.length - INITIAL_BARS), to: candles.length + RIGHT_SPACE });
        synced.rangeKey = key;
      }
    } else if (last) {
      main.update(toMainPoint(last, chartType));
      s.volume?.update(toVolumePoint(last, palette.volumeUp, palette.volumeDown));
      for (const k of lineKeys) {
        const point = indicatorData[k]?.[indicatorData[k].length - 1];
        if (s[k] && point) s[k].update(point);
      }
    }
    fullSyncRef.current = false;
    syncedRef.current = { ...synced, key, length: candles.length };
  }, [candles, indicatorData, chartType, palette, instrument.symbol, timeframe]);

  /* ---------------------------------------- opportunity + forecast layer */
  const lastTime = candles[candles.length - 1]?.time ?? null;
  useEffect(() => {
    const chart = chartRef.current;
    const main = mainRef.current;
    if (!chart || !main || !palette) return;

    if (priceLinesRef.current?.series === main) {
      for (const l of priceLinesRef.current.lines) main.removePriceLine(l);
    }
    priceLinesRef.current = null;

    const detected = opportunity && opportunity.status === 'detected' ? opportunity : null;
    const forecast = detected && showForecast ? (detected.forecast ?? []) : [];

    if (detected) {
      const level = (price: number, color: string, title: string) =>
        main.createPriceLine({ price, color, title, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true });
      priceLinesRef.current = {
        series: main,
        lines: [
          level(zoneMid(detected.takeProfitZone), palette.up, 'TP'),
          level(zoneMid(detected.entryZone), palette.accent, 'Entry'),
          level(zoneMid(detected.stopLossZone), palette.down, 'SL'),
        ],
      };
      const prices = [detected.takeProfitZone.high, detected.takeProfitZone.low, detected.stopLossZone.high, detected.stopLossZone.low];
      extraRangeRef.current = { min: Math.min(...prices), max: Math.max(...prices) };
      overlay.setState({
        fromTime: detected.signalCandleTime,
        zones: [
          { ...detected.takeProfitZone, fill: palette.zoneTp },
          { ...detected.entryZone, fill: palette.zoneEntry },
          { ...detected.stopLossZone, fill: palette.zoneSl },
        ],
        nowTime: lastTime,
        nowColor: palette.muted,
        forecastTint: forecast.length ? palette.forecastRegion : null,
      });
    } else {
      extraRangeRef.current = null;
      overlay.setState({ fromTime: null, zones: [], nowTime: lastTime, nowColor: palette.muted, forecastTint: null });
    }

    if (forecast.length) {
      if (!forecastRef.current) {
        forecastRef.current = chart.addSeries(LineSeries, {
          color: palette.forecast,
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          pointMarkersVisible: true,
          pointMarkersRadius: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerBackgroundColor: palette.forecast,
          priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
        });
      } else {
        forecastRef.current.applyOptions({ color: palette.forecast, crosshairMarkerBackgroundColor: palette.forecast });
      }
      forecastRef.current.setData(forecast.map((p) => ({ time: ts(p.time), value: p.value })));
    } else if (forecastRef.current) {
      chart.removeSeries(forecastRef.current);
      forecastRef.current = null;
    }
  }, [opportunity, showForecast, palette, lastTime, overlay, precision, chartType]);

  /* ------------------------------------------------------ view controls */
  const zoom = (factor: number) => {
    const scale = chartRef.current?.timeScale();
    const range = scale?.getVisibleLogicalRange();
    if (!scale || !range) return;
    const width = Math.max(10, (range.to - range.from) * factor);
    scale.setVisibleLogicalRange({ from: range.to - width, to: range.to });
  };
  const resetView = () => {
    const n = candlesRef.current.length;
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - INITIAL_BARS), to: n + RIGHT_SPACE });
  };

  const summary = useMemo(() => {
    const last = candles[candles.length - 1];
    const typeLabel = CHART_TYPES.find((c) => c.id === chartType)?.label ?? chartType;
    const parts = [
      `${provenance === 'demo' ? 'Simulated ' : ''}${instrument.display} ${timeframe} ${typeLabel.toLowerCase()} chart with ${candles.length} candles.`,
    ];
    if (last) parts.push(`Last price ${formatPrice(last.close, precision)} at ${formatDate(last.time * 1000, timeZone)} ${formatClock(last.time * 1000, timeZone, false)} ${timeZoneLabel(timeZone)}.`);
    if (opportunity?.status === 'detected') {
      parts.push(
        `AI opportunity ${opportunity.direction}, probability ${formatPercent(opportunity.probability)}, entry ${formatPrice(zoneMid(opportunity.entryZone), precision)}, stop-loss ${formatPrice(zoneMid(opportunity.stopLossZone), precision)}, take-profit ${formatPrice(zoneMid(opportunity.takeProfitZone), precision)}.`,
      );
    }
    return parts.join(' ');
    // Summary only needs to change when the last bar or the analysis changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastTime, candles.length, chartType, instrument, timeframe, opportunity, timeZone, provenance]);

  return (
    // A labelled group, not role="img": the canvas area contains the library's
    // attribution link, and interactive content must not sit inside an image.
    <div role="group" aria-label="Price chart" aria-describedby={summaryId} className="relative h-full min-h-0 w-full">
      <p id={summaryId} className="sr-only">
        {summary}
      </p>
      <div ref={containerRef} className="absolute inset-0" />
      <ChartLegend
        instrument={instrument}
        timeframe={timeframe}
        candles={candles}
        hover={hover}
        indicatorData={indicatorData}
        indicators={indicators}
        palette={palette}
        volumeKind={volumeKind}
        provenance={provenance}
        timeZone={timeZone}
        hasForecast={Boolean(opportunity?.status === 'detected' && showForecast && opportunity.forecast?.length)}
      />
      <div className="absolute top-2 right-[72px] z-10 flex gap-0.5 rounded-md border border-line bg-surface/90 p-0.5">
        <IconButton icon={ZoomIn} label="Zoom in" size="sm" onClick={() => zoom(0.7)} />
        <IconButton icon={ZoomOut} label="Zoom out" size="sm" onClick={() => zoom(1.4)} />
        <IconButton icon={Maximize2} label="Reset view to latest" size="sm" onClick={resetView} tooltipSide="left" />
      </div>
    </div>
  );
}

export const PriceChart = memo(PriceChartImpl);
