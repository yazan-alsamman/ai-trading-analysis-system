/**
 * Chart colours are read from the same CSS tokens as the rest of the UI, so
 * the canvas follows the active theme without a second colour definition.
 */
export interface ChartPalette {
  background: string;
  text: string;
  muted: string;
  grid: string;
  border: string;
  crosshair: string;
  up: string;
  down: string;
  accent: string;
  forecast: string;
  forecastSoft: string;
  zoneEntry: string;
  zoneTp: string;
  zoneSl: string;
  ind1: string;
  ind2: string;
  ind3: string;
  volumeUp: string;
  volumeDown: string;
  surfaceRaised: string;
  forecastRegion: string;
  price: string;
}

const VARS: Record<keyof ChartPalette, string> = {
  background: '--bg-surface',
  text: '--fg-secondary',
  muted: '--fg-muted',
  grid: '--chart-grid',
  border: '--line-subtle',
  crosshair: '--chart-crosshair',
  up: '--up',
  down: '--down',
  accent: '--accent',
  forecast: '--forecast',
  forecastSoft: '--forecast-soft',
  zoneEntry: '--chart-zone-entry',
  zoneTp: '--chart-zone-tp',
  zoneSl: '--chart-zone-sl',
  ind1: '--chart-ind-1',
  ind2: '--chart-ind-2',
  ind3: '--chart-ind-3',
  volumeUp: '--chart-vol-up',
  volumeDown: '--chart-vol-down',
  surfaceRaised: '--bg-raised',
  forecastRegion: '--chart-forecast-region',
  price: '--fg-primary',
};

export function readChartPalette(element: Element = document.documentElement): ChartPalette {
  const style = getComputedStyle(element);
  const palette = {} as ChartPalette;
  for (const [key, cssVar] of Object.entries(VARS) as [keyof ChartPalette, string][]) {
    palette[key] = style.getPropertyValue(cssVar).trim() || '#888888';
  }
  return palette;
}
