import { Badge } from '@/components/ui/Badge';
import { Markdown } from '@/components/ui/Markdown';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { evaluateLimits } from '@/domain/risk';
import { sessionStates, sessionSummary } from '@/domain/sessions';
import { FactorList } from '@/features/opportunity/FactorList';
import { LimitMeter } from '@/features/risk/LimitMeter';
import { CheckList } from '@/features/signals/SignalDetail';
import { buildDemoNews } from '@/fixtures/community';
import { cn } from '@/lib/cn';
import { formatMoney, formatNumber, formatPct, formatPercent, formatPrice, formatRiskReward, formatUnits } from '@/lib/format';
import { buildShowcase, SHOWCASE_ANCHOR, SHOWCASE_PROFILE, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';
import { ShowcaseChart } from './ShowcaseChart';

/**
 * Product previews for the marketing site. They render the APPLICATION's own
 * components (FactorList, CheckList, LimitMeter, Markdown…) with the showcase
 * data, so what visitors see matches the product exactly.
 */
function Frame({ title, tag, children, className }: { title: string; tag?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex h-full flex-col overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-float', className)}>
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <span aria-hidden className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <span key={i} className="size-2 rounded-full bg-line-strong" />
          ))}
        </span>
        <span className="ml-1 truncate text-sm font-semibold text-fg">{title}</span>
        <span className="ml-auto">{tag ?? <SourceTag kind="demo" />}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden p-4">{children}</div>
    </div>
  );
}

const anchorMs = SHOWCASE_ANCHOR * 1000;

export function MarketPreview() {
  const news = buildDemoNews(anchorMs).slice(0, 3);
  return (
    <Frame title="Market intelligence" tag={<SourceTag kind="demo" label="Sample content" />}>
      <p className="eyebrow">Sessions · {sessionSummary(anchorMs)}</p>
      <ul className="mt-2 grid grid-cols-4 gap-2">
        {sessionStates(anchorMs).map((s) => (
          <li key={s.id} className={cn('rounded-lg border px-2 py-1.5 text-center text-xs', s.open ? 'border-accent/50 bg-accent-soft text-fg' : 'border-line text-fg-3')}>
            {s.label}
            <span className="block text-fg-3">{s.open ? 'Open' : 'Closed'}</span>
          </li>
        ))}
      </ul>
      <ul className="mt-4 flex flex-col divide-y divide-line">
        {news.map((n) => (
          <li key={n.id} className="py-2.5">
            <div className="flex items-center gap-2">
              <Badge tone={n.impact === 'high' ? 'warning' : 'neutral'}>{n.impact} impact</Badge>
              <span className="truncate text-xs text-fg-3">{n.symbols.map((s) => getInstrument(s).display).join(' · ')}</span>
            </div>
            <p className="mt-1 line-clamp-2 text-sm text-fg-2">{n.title}</p>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export function ChartPreview() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  return (
    <Frame title={`${inst.display} · ${SHOWCASE_TIMEFRAME} · Workspace`}>
      <ShowcaseChart
        candles={s.candles}
        opportunity={s.opportunity}
        timeframe={SHOWCASE_TIMEFRAME}
        precision={inst.pricePrecision}
        variant="candles"
        mode="steps"
        label="Workspace preview: simulated candles, the NOW boundary, the demo model's levels and projection."
      />
    </Frame>
  );
}

export function ResearchPreview() {
  const s = buildShowcase();
  const o = s.opportunity;
  return (
    <Frame title="AI research panel">
      <div className="flex items-center gap-2">
        <Badge tone="forecast">Opportunity detected</Badge>
        <DirectionBadge direction={o.direction} />
        <span className="num ml-auto text-lg text-forecast">{formatPercent(o.probability)}</span>
      </div>
      <p className="mt-1 text-xs text-fg-3">Probability the target is reached before the stop · reward : risk {formatRiskReward(o.riskReward)}</p>
      <div className="mt-4">
        <FactorList factors={o.factors.slice(0, 3)} direction={o.direction} />
      </div>
    </Frame>
  );
}

export function SignalsPreview() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  return (
    <Frame title="Personalised signal">
      <div className="mb-3 flex items-center gap-2">
        <span className="font-medium text-fg">{inst.display}</span>
        <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
        <DirectionBadge direction={s.opportunity.direction} />
        <Badge tone="accent" className="ml-auto">
          Matches your profile
        </Badge>
      </div>
      <CheckList checks={s.evaluation.checks.filter((c) => c.group !== 'data').slice(0, 5)} />
    </Frame>
  );
}

export function RiskPreview() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const daily = evaluateLimits(SHOWCASE_PROFILE, s.risk.monetaryRisk).find((l) => l.id === 'open_risk');
  return (
    <Frame title="Capital & risk" tag={<SourceTag kind="user" label="Example inputs" />}>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line">
        {[
          ['Position size', formatUnits(s.risk.units, inst.base)],
          ['Money at risk', formatMoney(s.risk.monetaryRisk, 'USD')],
          ['Potential reward', formatMoney(s.risk.potentialReward, 'USD')],
          ['Of capital', formatPct(s.risk.riskPctOfCapital)],
        ].map(([k, v]) => (
          <div key={k} className="bg-surface px-3 py-2.5">
            <dt className="text-xs text-fg-3">{k}</dt>
            <dd className="num mt-0.5 text-md text-fg">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-fg-3">
        Plan: entry {formatPrice(s.plan.entry, inst.pricePrecision)} · stop {formatPrice(s.plan.stop, inst.pricePrecision)} · $25,000 example capital at 1 %
      </p>
      {daily && (
        <div className="mt-4">
          <LimitMeter check={daily} currency="USD" />
        </div>
      )}
    </Frame>
  );
}

export function InsightsPreview() {
  const { stats } = buildShowcase();
  const bins = stats.calibration.filter((b) => b.count > 0);
  return (
    <Frame title="Performance insights" tag={<SourceTag kind="demo" label="Simulated history" />}>
      <dl className="grid grid-cols-3 gap-3">
        <div>
          <dt className="text-xs text-fg-3">Hit rate</dt>
          <dd className="num text-xl text-fg">{formatPercent(stats.hitRate)}</dd>
        </div>
        <div>
          <dt className="text-xs text-fg-3">Brier score</dt>
          <dd className="num text-xl text-fg">{formatNumber(stats.brierScore, 3)}</dd>
        </div>
        <div>
          <dt className="text-xs text-fg-3">Resolved</dt>
          <dd className="num text-xl text-fg">{stats.resolved}</dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-fg-3">Calibration — stated probability vs observed rate</p>
      <div aria-hidden className="mt-2 flex h-24 items-end gap-1.5">
        {bins.map((b) => (
          <div key={b.from} className="relative flex-1">
            <div className="rounded-t-sm bg-forecast/30" style={{ height: `${b.meanPredicted * 96}px` }} />
            <div className="absolute inset-x-1 bottom-0 rounded-t-sm bg-fg-3" style={{ height: `${b.observedRate * 96}px` }} />
          </div>
        ))}
      </div>
    </Frame>
  );
}

export function AssistantPreview() {
  const { assistant } = buildShowcase();
  return (
    <Frame title="Assistant" tag={<SourceTag kind="demo" label="Rule-based demo" />}>
      <p className="ml-auto w-max max-w-[85%] rounded-2xl rounded-tr-sm bg-selected px-3 py-1.5 text-sm text-fg">What would invalidate this projection?</p>
      <div className="mt-3 max-h-[260px] overflow-hidden [mask-image:linear-gradient(to_bottom,black_75%,transparent)]">
        <Markdown source={assistant.content} className="text-xs leading-5" />
      </div>
    </Frame>
  );
}

/** Same order as MODULES in layouts/navigation.ts (01–07). */
export const MODULE_PREVIEWS = [MarketPreview, ChartPreview, ResearchPreview, RiskPreview, SignalsPreview, InsightsPreview, AssistantPreview] as const;
