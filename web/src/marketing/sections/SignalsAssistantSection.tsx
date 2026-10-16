import { Bot, CircleCheck, CircleDashed, CircleX } from 'lucide-react';
import { useRef } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Markdown } from '@/components/ui/Markdown';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatPercent, formatRiskReward } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useInView } from '@/motion/runtime';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const ICON = { pass: CircleCheck, fail: CircleX, not_evaluated: CircleDashed } as const;

export function SignalsAssistantSection() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const chatRef = useRef<HTMLDivElement>(null);
  const chatInView = useInView(chatRef);

  return (
    <section id="signals" data-section aria-labelledby="signals-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <p className="eyebrow mb-3">05 · Personalised research</p>
        <RevealText as="h2" id="signals-title" className="display max-w-3xl text-d3 text-fg sm:text-d2" lines={['Filtered by your rules.', <em key="e">Questioned on the evidence.</em>]} />

        <div className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
          {/* Personalised signal */}
          <Reveal variant="rise" className="flex flex-col rounded-2xl border border-line bg-surface p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-md font-semibold text-fg">Personalised signals</p>
                <p className="mt-1 max-w-sm text-sm text-fg-2">Your saved profile is applied to what the model returned. Every check is shown with the actual values — nothing is hidden behind a score.</p>
              </div>
              <SourceTag kind="demo" />
            </div>
            <div className="mt-6 rounded-xl border border-line-strong bg-inset p-4">
              <div className="flex items-center gap-2">
                <span className="font-medium text-fg">{inst.display}</span>
                <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
                <DirectionBadge direction={s.opportunity.direction} />
                <span className="num ml-auto text-sm text-forecast">{formatPercent(s.opportunity.probability)}</span>
                <span className="num text-sm text-fg-2">{formatRiskReward(s.opportunity.riskReward)}</span>
              </div>
              <ul className="mt-4 flex flex-col gap-2.5">
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
            </div>
          </Reveal>

          {/* Assistant */}
          <Reveal variant="rise" delay={120} className="flex flex-col rounded-2xl border border-line bg-surface p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-md font-semibold text-fg">AI assistant</p>
                <p className="mt-1 max-w-sm text-sm text-fg-2">Ask what the model saw, what would prove it wrong, or what a trade means for your capital. It may only use the data you can see.</p>
              </div>
              <SourceTag kind="demo" label="Rule-based demo" detail="No language model is connected. These are the demo assistant's actual, rule-based answers." />
            </div>
            <div ref={chatRef} className="mt-6 flex flex-1 flex-col gap-3 rounded-xl border border-line-strong bg-inset p-4" data-play={chatInView}>
              <p className="m-in ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-selected px-3.5 py-2 text-sm text-fg" style={{ '--at': '150ms' } as React.CSSProperties}>
                What would invalidate this projection?
              </p>
              <div className="m-in flex gap-3" style={{ '--at': '700ms' } as React.CSSProperties}>
                <span aria-hidden className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-forecast/40 bg-forecast-soft text-forecast">
                  <Bot className="size-3.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <Markdown source={s.assistant.content} className="text-xs leading-5" />
                  <p className="mt-2 text-xs text-fg-3">Rule-based, not a language model · used: {s.assistant.contextUsed.join(', ')}</p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
