import { Layers, Sparkles, SlidersHorizontal } from 'lucide-react';
import { Popover } from '@/components/ui/Popover';
import { Checkbox } from '@/components/ui/Form';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { INDICATORS, type IndicatorId } from '@/domain/indicators';
import { CHART_TYPES, TIMEFRAMES, type ChartType, type Timeframe } from '@/domain/market';
import { cn } from '@/lib/cn';

interface Props {
  timeframe: Timeframe;
  chartType: ChartType;
  indicators: IndicatorId[];
  showOverlay: boolean;
  showForecast: boolean;
  onTimeframe: (tf: Timeframe) => void;
  onChartType: (type: ChartType) => void;
  onIndicators: (ids: IndicatorId[]) => void;
  onShowOverlay: (v: boolean) => void;
  onShowForecast: (v: boolean) => void;
}

function Toggle({ pressed, onClick, children, label }: { pressed: boolean; onClick: () => void; children: React.ReactNode; label: string }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      title={label}
      onClick={onClick}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-sm font-medium transition-colors duration-150',
        // Quiet when on: a selected surface + violet icon, not a filled violet button.
        pressed ? 'border-line-strong bg-selected text-fg [&_svg]:text-forecast' : 'border-line text-fg-3 hover:bg-hover hover:text-fg',
      )}
    >
      {children}
    </button>
  );
}

export function ChartToolbar(props: Props) {
  const { timeframe, chartType, indicators, showOverlay, showForecast } = props;
  const toggleIndicator = (id: IndicatorId, on: boolean) =>
    props.onIndicators(on ? [...indicators, id] : indicators.filter((x) => x !== id));

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface px-3 py-2">
      <SegmentedControl
        label="Timeframe"
        value={timeframe}
        onChange={props.onTimeframe}
        options={TIMEFRAMES.map((t) => ({ value: t.id, label: t.label, title: `${t.label} — ${t.description}` }))}
      />
      <SegmentedControl label="Chart type" value={chartType} onChange={props.onChartType} options={CHART_TYPES.map((c) => ({ value: c.id, label: c.label }))} />

      <Popover
        label="Indicators"
        trigger={(t) => (
          <button
            type="button"
            {...t}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-sm font-medium text-fg-2 hover:bg-hover hover:text-fg"
          >
            <SlidersHorizontal aria-hidden className="size-4" />
            Indicators
            {indicators.length > 0 && <span className="num rounded-sm bg-selected px-1 text-xs text-fg">{indicators.length}</span>}
          </button>
        )}
      >
        <fieldset className="flex flex-col gap-2.5 p-2">
          <legend className="mb-1 text-xs font-medium text-fg-3">Technical indicators</legend>
          {INDICATORS.map((ind) => (
            <Checkbox
              key={ind.id}
              label={ind.label}
              description={ind.description}
              checked={indicators.includes(ind.id)}
              onChange={(e) => toggleIndicator(ind.id, e.target.checked)}
            />
          ))}
        </fieldset>
      </Popover>

      <div className="ml-auto flex items-center gap-2">
        <span className="hidden text-xs text-fg-3 xl:inline">AI layer</span>
        <Toggle pressed={showOverlay} onClick={() => props.onShowOverlay(!showOverlay)} label="Show AI entry, stop-loss and take-profit zones on the chart">
          <Layers aria-hidden className="size-4" />
          Zones
        </Toggle>
        <Toggle pressed={showForecast} onClick={() => props.onShowForecast(!showForecast)} label="Show the AI forecast path on the chart">
          <Sparkles aria-hidden className="size-4" />
          Forecast
        </Toggle>
      </div>
    </div>
  );
}
