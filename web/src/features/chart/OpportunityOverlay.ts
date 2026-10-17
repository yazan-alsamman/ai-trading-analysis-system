import type {
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';

/** The fancy-canvas render target type, derived so we need no direct dependency. */
type RenderTarget = Parameters<IPrimitivePaneRenderer['draw']>[0];

export interface OverlayZone {
  low: number;
  high: number;
  fill: string;
}

export interface OverlayState {
  /** Zones start at this candle (epoch s). */
  fromTime: number | null;
  zones: OverlayZone[];
  /** Boundary between observed data and forecast (epoch s). */
  nowTime: number | null;
  nowColor: string;
  /** Tint for the forecast region right of `nowTime`; null = no forecast shown. */
  forecastTint: string | null;
}

const EMPTY: OverlayState = { fromTime: null, zones: [], nowTime: null, nowColor: '#888', forecastTint: null };

/**
 * Series primitive that paints AI opportunity zones (entry / SL / TP), the
 * "Now" boundary and a tint over the forecast region. Drawn below the
 * candles so price data is never obscured.
 */
export class OpportunityOverlay implements ISeriesPrimitive<Time> {
  private chart: IChartApiBase<Time> | null = null;
  private series: ISeriesApi<SeriesType, Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private state: OverlayState = EMPTY;
  private readonly view: IPrimitivePaneView;

  constructor() {
    const renderer: IPrimitivePaneRenderer = { draw: (target) => this.draw(target) };
    this.view = { zOrder: () => 'bottom', renderer: () => renderer };
  }

  attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>): void {
    this.chart = chart;
    this.series = series;
    this.requestUpdate = requestUpdate;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [this.view];
  }

  setState(state: OverlayState | null): void {
    this.state = state ?? EMPTY;
    this.requestUpdate?.();
  }

  private x(time: number | null): number | null {
    if (time === null || !this.chart) return null;
    return this.chart.timeScale().timeToCoordinate(time as UTCTimestamp);
  }

  private draw(target: RenderTarget): void {
    const { chart, series, state } = this;
    if (!chart || !series) return;

    target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hpr, verticalPixelRatio: vpr }) => {
      const width = bitmapSize.width;
      const nowX = this.x(state.nowTime);

      if (state.forecastTint && nowX !== null) {
        ctx.fillStyle = state.forecastTint;
        ctx.fillRect(Math.round(nowX * hpr), 0, width - Math.round(nowX * hpr), bitmapSize.height);
      }

      const fromX = this.x(state.fromTime);
      if (fromX !== null) {
        // Zone names are carried by the price-line titles (TP / Entry / SL) on the axis.
        const left = Math.max(0, Math.round(fromX * hpr));
        for (const zone of state.zones) {
          const yTop = series.priceToCoordinate(zone.high);
          const yBottom = series.priceToCoordinate(zone.low);
          if (yTop === null || yBottom === null) continue;
          const top = Math.round(Math.min(yTop, yBottom) * vpr);
          const height = Math.max(Math.round(Math.abs(yBottom - yTop) * vpr), Math.round(2 * vpr));
          ctx.fillStyle = zone.fill;
          ctx.fillRect(left, top, width - left, height);
        }
      }

      if (nowX !== null) {
        const x = Math.round(nowX * hpr) + 0.5;
        ctx.strokeStyle = state.nowColor;
        ctx.lineWidth = Math.max(1, Math.round(hpr));
        ctx.setLineDash([4 * hpr, 4 * hpr]);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, bitmapSize.height);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = state.nowColor;
        ctx.font = `600 ${Math.round(10 * vpr)}px Inter Variable, system-ui, sans-serif`;
        ctx.textBaseline = 'bottom';
        // Bottom of the pane: the top-right corner is reserved for chart controls.
        ctx.fillText('NOW', x + Math.round(5 * hpr), bitmapSize.height - Math.round(6 * vpr));
      }
    });
  }
}
