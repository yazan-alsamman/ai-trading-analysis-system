import { CircleCheck, CircleDashed, CircleX } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatPercent, formatRiskReward } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const ICON = { pass: CircleCheck, fail: CircleX, not_evaluated: CircleDashed } as const;

/** Scene: one model output passed through the visitor's own signal profile, check by check. */
export function SignalsSection() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);

  return (
    <section id="signals" data-section aria-labelledby="signals-title" className="border-b border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:items-center">
        <div>
          <p className="eyebrow mb-3">06 · Personalised signals</p>
          <RevealText as="h2" id="signals-title" className="display max-w-xl text-d3 text-fg sm:text-d2" lines={['Filtered by', <em key="e">your own rules.</em>]} />
          <Reveal as="p" delay={150} className="mt-4 max-w-xl text-md text-fg-2">
            Your saved profile — instruments, timeframes, minimum probability, reward : risk and your risk limits — is applied to what the model returned. Every check is
            shown with the actual values; nothing is hidden behind a score.
          </Reveal>
        </div>

        <Reveal variant="scale" className="rounded-2xl border border-line-strong bg-surface p-5 shadow-float">
          <div className="flex items-center gap-2">
            <span className="font-medium text-fg">{inst.display}</span>
            <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
            <DirectionBadge direction={s.opportunity.direction} />
            <span className="num ml-auto text-sm text-forecast">{formatPercent(s.opportunity.probability)}</span>
            <span className="num text-sm text-fg-2">{formatRiskReward(s.opportunity.riskReward)}</span>
            <SourceTag kind="demo" />
          </div>
          <ul className="mt-4 flex flex-col gap-2.5 border-t border-line pt-4">
            {s.evaluation.checks.map((c, i) => {
              const Icon = ICON[c.status];
              return (
                <Reveal as="li" key={c.id} index={i} stagger={90} delay={200} variant="left" className="flex gap-2.5">
                  <Icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', c.status === 'pass' ? 'text-accent' : c.status === 'fail' ? 'text-danger' : 'text-fg-3')} />
                  <span className="min-w-0">
                    <span className="block text-sm text-fg">{c.label}</span>
                    <span className="block truncate text-xs text-fg-3">{c.detail}</span>
                  </span>
                </Reveal>
              );
            })}
          </ul>
          <Reveal delay={1200} className="mt-4 border-t border-line pt-3">
            <Badge tone={s.evaluation.matches ? 'accent' : 'neutral'}>{s.evaluation.matches ? 'Matches your profile' : 'Outside your profile'}</Badge>
          </Reveal>
        </Reveal>
      </div>
    </section>
  );
}
