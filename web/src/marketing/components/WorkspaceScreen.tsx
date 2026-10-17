import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { ALL_NAV } from '@/layouts/navigation';
import { cn } from '@/lib/cn';
import { formatMoney, formatPct, formatPercent, formatProbabilityBand, formatRiskReward, formatUnits } from '@/lib/format';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';
import { ShowcaseChart } from './ShowcaseChart';

const OTHER_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY'] as const;

/**
 * The research workspace as it appears inside the 3D laptop: the app's
 * navigation, chart, model output, evidence and risk plan, rendered with the
 * application's own components and the showcase (simulated) data.
 * Authored at 1000 × 625 px and scaled to the screen.
 */
export function WorkspaceScreen() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const o = s.opportunity;
  const factors = [...o.factors].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 4);
  const maxC = Math.max(...factors.map((f) => Math.abs(f.contribution)), 0.0001);
  const nav = ALL_NAV.filter((n) => ['/overview', '/workspace', '/signals', '/risk', '/assistant', '/insights'].includes(n.to));

  return (
    <div className="screen-canvas flex flex-col bg-canvas text-fg">
      {/* App bar */}
      <div className="flex h-11 shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
        <span className="size-2.5 rounded-full bg-accent" />
        <span className="text-sm font-semibold">AI Trading Assistance</span>
        <span className="ml-3 flex gap-1">
          {nav.map((n) => (
            <span key={n.to} className={cn('rounded-full px-2.5 py-1 text-xs', n.to === '/workspace' ? 'bg-selected text-fg' : 'text-fg-3')}>
              {n.label}
            </span>
          ))}
        </span>
        <SourceTag kind="demo" className="ml-auto" />
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_292px]">
        {/* Chart area */}
        <div className="flex min-w-0 flex-col border-r border-line">
          <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
            <span className="rounded-md bg-selected px-2 py-0.5 text-sm font-semibold">{inst.display}</span>
            {OTHER_SYMBOLS.map((sym) => (
              <span key={sym} className="px-1.5 text-sm text-fg-3">
                {getInstrument(sym).display}
              </span>
            ))}
            <span className="ml-auto flex gap-1 text-xs">
              {['15m', '1h', '4h', '1d'].map((tf) => (
                <span key={tf} className={cn('num rounded-md px-2 py-0.5', tf === SHOWCASE_TIMEFRAME ? 'bg-selected text-fg' : 'text-fg-3')}>
                  {tf}
                </span>
              ))}
            </span>
          </div>
          <div className="min-h-0 flex-1 px-2 pt-3">
            <ShowcaseChart
              candles={s.candles}
              opportunity={o}
              timeframe={SHOWCASE_TIMEFRAME}
              precision={inst.pricePrecision}
              variant="candles"
              mode="steps"
              label={`Simulated ${inst.display} ${SHOWCASE_TIMEFRAME} candles with the demo model's levels and projection.`}
            />
          </div>
          <div className="flex gap-4 border-t border-line px-4 py-2 text-xs text-fg-3">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-accent" /> Observed (simulated)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-4 border-t-2 border-dashed border-forecast" /> Model projection
            </span>
          </div>
        </div>

        {/* Research rail */}
        <div className="flex min-h-0 flex-col gap-3 overflow-hidden bg-surface/40 p-3">
          <div className="rounded-xl border border-line bg-surface p-3">
            <div className="flex items-center gap-2">
              <p className="eyebrow">Model output</p>
              <DirectionBadge direction={o.direction} className="ml-auto" />
            </div>
            <p className="num mt-2 text-[2rem] leading-none text-forecast">{formatPercent(o.probability)}</p>
            <p className="mt-1 text-xs text-fg-3">target before stop · band {formatProbabilityBand(o.confidenceBand)} · {formatRiskReward(o.riskReward)}</p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-3">
            <p className="eyebrow">Evidence</p>
            <ul className="mt-2 flex flex-col gap-2">
              {factors.map((f) => (
                <li key={f.id}>
                  <div className="flex justify-between gap-2 text-xs">
                    <span className="truncate text-fg-2">{f.label}</span>
                    <span className="num text-fg-3">
                      {f.contribution >= 0 ? '+' : '−'}
                      {Math.abs(f.contribution).toFixed(2)}
                    </span>
                  </div>
                  <span className="mt-1 block h-1 rounded-full bg-line">
                    <span className={cn('block h-full rounded-full', f.contribution >= 0 ? 'bg-accent' : 'bg-down')} style={{ width: `${(Math.abs(f.contribution) / maxC) * 100}%` }} />
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-line bg-surface p-3">
            <div className="flex items-center justify-between">
              <p className="eyebrow">Risk plan</p>
              <span className="text-xs text-fg-3">$25,000 · 1 %</span>
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-y-1 text-xs">
              <dt className="text-fg-3">Position</dt>
              <dd className="num text-right">{formatUnits(s.risk.units, inst.base)}</dd>
              <dt className="text-fg-3">Loss at stop</dt>
              <dd className="num text-right text-down">{formatMoney(s.risk.monetaryRisk, 'USD')}</dd>
              <dt className="text-fg-3">Of capital</dt>
              <dd className="num text-right">{formatPct(s.risk.riskPctOfCapital)}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
