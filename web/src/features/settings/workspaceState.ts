import { z } from 'zod';
import { isIndicatorId, type IndicatorId } from '@/domain/indicators';
import type { BackendInstrument } from '@/domain/strategies';
import { TIMEFRAMES, type ChartType, type Timeframe } from '@/domain/market';
import type { Workspace } from '@/domain/preferences';
import type { WorkspaceStateDoc } from '@/domain/serverWorkspaces';

/**
 * Mapping between a browser workspace (one chart) and the server's workspace
 * state document (docs/workspaces.md, schema_version 1). The server document
 * can hold more than the web client models (several panels, drawings,
 * strategy overlays, a watchlist); what cannot be mapped is reported, never
 * silently invented.
 */

/** Browser indicator ↔ server indicator registry entry (libs/indicators). `volume` is a chart feature, not a server indicator. */
const INDICATOR_MAP: Partial<Record<IndicatorId, { name: string; params: Record<string, number> }>> = {
  sma20: { name: 'sma', params: { length: 20 } },
  ema50: { name: 'ema', params: { length: 50 } },
  bb20: { name: 'bollinger', params: { length: 20, std: 2 } },
  rsi14: { name: 'rsi', params: { length: 14 } },
};

const SERVER_CHART_TYPES: readonly ChartType[] = ['candles', 'bars', 'line', 'area'];

export interface MappedState {
  state: WorkspaceStateDoc;
  /** Things in the browser workspace the server document cannot hold. */
  skipped: string[];
}

export function toServerState(ws: Workspace, instruments: readonly BackendInstrument[]): MappedState {
  const skipped: string[] = [];
  const instrument = instruments.find((i) => i.webSymbol === ws.symbol);
  if (!instrument) skipped.push(`instrument ${ws.symbol} (not on this server)`);
  const indicators = ws.indicators.flatMap((id) => {
    const m = INDICATOR_MAP[id];
    // The volume histogram is a display setting of this website's chart, kept in the browser.
    if (id === 'volume') return [];
    if (!m) {
      skipped.push(`${id} overlay`);
      return [];
    }
    return [{ id: `i_${id}`, name: m.name, params: m.params, visible: true }];
  });
  return {
    state: {
      layout: { type: '1x1' },
      sync: { crosshair: true, timeframe: false, instrument: false },
      panels: [
        {
          id: 'p1',
          instrument_id: instrument?.id ?? null,
          timeframe: ws.timeframe,
          chart_type: ws.chartType,
          indicators,
          strategies: [],
          drawings: [],
        },
      ],
      watchlist: [],
      active_panel: 'p1',
    },
    skipped,
  };
}

const PanelDoc = z.object({
  id: z.string(),
  instrument_id: z.string().nullable().optional(),
  timeframe: z.string().optional(),
  chart_type: z.string().optional(),
  indicators: z.array(z.object({ name: z.string(), params: z.record(z.string(), z.unknown()).optional() })).optional(),
  strategies: z.array(z.unknown()).optional(),
  drawings: z.array(z.unknown()).optional(),
});
const StateDoc = z.object({ panels: z.array(PanelDoc).optional(), active_panel: z.string().optional() });

export interface MappedWorkspace {
  patch: Partial<Pick<Workspace, 'symbol' | 'timeframe' | 'chartType' | 'indicators'>>;
  /** Parts of the server workspace the browser workspace cannot show. */
  skipped: string[];
}

/**
 * The active (or first) panel of a server workspace, as a browser workspace
 * patch. `keepVolume`: whether the browser workspace shows the volume histogram
 * (not part of the server document).
 */
export function fromServerState(state: WorkspaceStateDoc, instruments: readonly BackendInstrument[], keepVolume = true): MappedWorkspace {
  const skipped: string[] = [];
  const parsed = StateDoc.safeParse(state);
  const panels = parsed.success ? (parsed.data.panels ?? []) : [];
  const panel = panels.find((p) => p.id === (parsed.success ? parsed.data.active_panel : undefined)) ?? panels[0];
  if (!panel) return { patch: {}, skipped: ['the workspace has no chart panel'] };
  if (panels.length > 1) skipped.push(`${panels.length - 1} other chart panel${panels.length > 2 ? 's' : ''} (this website shows one chart)`);

  const patch: MappedWorkspace['patch'] = {};
  const instrument = panel.instrument_id ? instruments.find((i) => i.id === panel.instrument_id) : undefined;
  if (instrument?.webSymbol) patch.symbol = instrument.webSymbol;
  else if (panel.instrument_id) skipped.push(`instrument ${instrument?.symbol ?? 'unknown'} (not charted by this website)`);

  const tf = TIMEFRAMES.find((t) => t.id === panel.timeframe);
  if (tf) patch.timeframe = tf.id as Timeframe;
  else if (panel.timeframe) skipped.push(`timeframe ${panel.timeframe}`);

  const chartType = panel.chart_type === 'heikin_ashi' ? 'candles' : SERVER_CHART_TYPES.find((c) => c === panel.chart_type);
  if (chartType) patch.chartType = chartType;
  if (panel.chart_type === 'heikin_ashi') skipped.push('Heikin-Ashi candles (shown as regular candles)');

  const indicators: IndicatorId[] = keepVolume ? ['volume'] : [];
  for (const ind of panel.indicators ?? []) {
    const match = (Object.entries(INDICATOR_MAP) as [IndicatorId, { name: string; params: Record<string, number> }][]).find(
      ([, m]) => m.name === ind.name && Object.entries(m.params).every(([k, v]) => ind.params?.[k] === undefined || Number(ind.params?.[k]) === v),
    );
    if (match && isIndicatorId(match[0])) indicators.push(match[0]);
    else skipped.push(`${ind.name} indicator`);
  }
  patch.indicators = [...new Set(indicators)];
  if (panel.strategies?.length) skipped.push('strategy overlays');
  if (panel.drawings?.length) skipped.push('drawings');
  return { patch, skipped };
}
