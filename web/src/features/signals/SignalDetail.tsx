import { ArrowUpRight, Bot, CircleCheck, CircleDashed, CircleX, Scale } from 'lucide-react';
import { Link } from 'react-router';
import { Badge } from '@/components/ui/Badge';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { RISK_LABELS, SETUP_LABELS, type Opportunity } from '@/domain/opportunity';
import { planFromOpportunity } from '@/domain/risk';
import type { CheckGroup, SignalCheck, SignalEvaluation } from '@/domain/signalProfile';
import { cn } from '@/lib/cn';
import { formatDateTime, formatPercent, formatPrice, formatProbabilityBand, formatR, formatRiskReward, timeZoneLabel } from '@/lib/format';
import { FactorList } from '../opportunity/FactorList';

const CHECK_ICON = {
  pass: { icon: CircleCheck, cls: 'text-fg-2', word: 'Passed' },
  fail: { icon: CircleX, cls: 'text-danger', word: 'Failed' },
  not_evaluated: { icon: CircleDashed, cls: 'text-fg-3', word: 'Not evaluated' },
} as const;

const GROUP_TITLE: Record<CheckGroup, string> = {
  data: 'Data quality',
  preference: 'Your preferences',
  risk: 'Your risk limits',
};

export function CheckList({ checks }: { checks: SignalCheck[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {checks.map((c) => {
        const m = CHECK_ICON[c.status];
        return (
          <li key={c.id} className="flex gap-2.5">
            <m.icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', m.cls)} />
            <div className="min-w-0">
              <p className="text-sm text-fg">
                {c.label} <span className={cn('text-xs', m.cls)}>· {m.word}</span>
              </p>
              <p className="text-xs text-fg-3">{c.detail}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Step({ n, title, tag, children }: { n: number; title: string; tag?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border-b border-line px-5 py-4 last:border-b-0">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="num inline-flex size-5 items-center justify-center rounded-full border border-line-strong text-xs text-fg-2">{n}</span>
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {tag}
      </div>
      {children}
    </section>
  );
}

/** Provenance of one signal: what the model returned vs what the user's profile did with it. */
export function SignalDetail({ opportunity: o, evaluation, timeZone, onOpenWorkspace }: { opportunity: Opportunity; evaluation: SignalEvaluation; timeZone: string; onOpenWorkspace: () => void }) {
  const inst = getInstrument(o.symbol);
  const p = inst.pricePrecision;
  const detected = o.status === 'detected';
  const plan = planFromOpportunity(o);
  const riskHref = plan
    ? `/risk?symbol=${o.symbol}&tf=${o.timeframe}&entry=${plan.entry.toFixed(p)}&stop=${plan.stop.toFixed(p)}&target=${plan.target.toFixed(p)}&origin=model`
    : `/risk?symbol=${o.symbol}`;
  const askHref = `/assistant?symbol=${o.symbol}&tf=${o.timeframe}&q=${encodeURIComponent('Summarise the evidence behind this signal')}`;
  const groups = (['preference', 'risk', 'data'] as const).map((g) => ({ g, checks: evaluation.checks.filter((c) => c.group === g) })).filter((x) => x.checks.length);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
        {detected ? <DirectionBadge direction={o.direction} /> : <Badge>No opportunity</Badge>}
        <Badge tone={evaluation.matches ? 'accent' : 'neutral'}>{evaluation.matches ? 'Matches your profile' : 'Outside your profile'}</Badge>
        <span className="ml-auto text-xs text-fg-3">
          {evaluation.passed} passed · {evaluation.failed} failed{evaluation.notEvaluated ? ` · ${evaluation.notEvaluated} not evaluated` : ''}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Step n={1} title="What the model returned" tag={<SourceTag kind={o.provenance === 'demo' ? 'demo' : 'model'} />}>
          {detected ? (
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line text-sm">
              {[
                ['Probability (TP before SL)', <span className="num text-forecast">{formatPercent(o.probability)}</span>],
                ['Confidence band', <span className="num">{o.confidenceBand ? formatProbabilityBand(o.confidenceBand) : 'Not supplied'}</span>],
                ['Entry zone', <span className="num">{`${formatPrice(o.entryZone.low, p)} – ${formatPrice(o.entryZone.high, p)}`}</span>],
                ['Stop-loss zone', <span className="num">{`${formatPrice(o.stopLossZone.low, p)} – ${formatPrice(o.stopLossZone.high, p)}`}</span>],
                ['Take-profit zone', <span className="num">{`${formatPrice(o.takeProfitZone.low, p)} – ${formatPrice(o.takeProfitZone.high, p)}`}</span>],
                ['Reward : risk · EV', <span className="num">{`${formatRiskReward(o.riskReward)} · ${formatR(o.expectedValueR)}`}</span>],
                ['Setup', SETUP_LABELS[o.setupType]],
                ['Risk level', RISK_LABELS[o.riskLevel]],
              ].map(([k, v], i) => (
                <div key={i} className="bg-surface px-3 py-2">
                  <dt className="text-xs text-fg-3">{k}</dt>
                  <dd className="mt-0.5 text-fg">{v}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-fg-2">The model returned “no opportunity”. No levels were produced, so there is nothing to size.</p>
          )}
        </Step>

        {groups.map(({ g, checks }, i) => (
          <Step key={g} n={i + 2} title={GROUP_TITLE[g]} tag={g === 'data' ? undefined : <SourceTag kind="user" label={g === 'risk' ? 'Your limits' : 'Your profile'} />}>
            <CheckList checks={checks} />
          </Step>
        ))}

        <Step n={groups.length + 2} title="Supporting evidence" tag={<SourceTag kind={o.provenance === 'demo' ? 'demo' : 'model'} />}>
          {o.factors.length ? <FactorList factors={o.factors} direction={o.direction} /> : <p className="text-sm text-fg-3">The model supplied no factor explanations.</p>}
        </Step>

        <Step n={groups.length + 3} title="Timing and model">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
            <dt className="text-fg-3">Generated</dt>
            <dd className="num text-fg-2">
              {formatDateTime(o.generatedAt, timeZone)} {timeZoneLabel(timeZone)}
            </dd>
            <dt className="text-fg-3">Valid until</dt>
            <dd className="num text-fg-2">
              {formatDateTime(o.validUntil, timeZone)} {timeZoneLabel(timeZone)}
            </dd>
            <dt className="text-fg-3">Model version</dt>
            <dd className="text-fg-2">{o.modelVersion}</dd>
          </dl>
        </Step>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-line px-5 py-3">
        <button type="button" onClick={onOpenWorkspace} className={buttonClasses({ variant: 'primary' })}>
          <ArrowUpRight aria-hidden className="size-4" /> Open in workspace
        </button>
        {plan && (
          <Link to={riskHref} className={buttonClasses({ variant: 'secondary' })}>
            <Scale aria-hidden className="size-4" /> Size this trade
          </Link>
        )}
        <Link to={askHref} className={buttonClasses({ variant: 'ghost' })}>
          <Bot aria-hidden className="size-4" /> Ask the assistant
        </Link>
      </div>
    </div>
  );
}
