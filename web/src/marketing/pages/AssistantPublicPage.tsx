import { ArrowRight, Check, FlaskConical, Minus } from 'lucide-react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';
import { formatDateTime, formatPercent, formatPrice, formatRiskReward } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { PublicAssistant } from '../assistant/PublicAssistant';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const CAN = [
  'Summarise a model output: direction, probability, zones, reward : risk',
  'List the conditions that would invalidate it',
  'Size the plan for an account and show the limit checks',
  'Lay out the evidence the model attached, factor by factor',
  'Name what is missing or unverified',
  'Define terms such as Brier score, ATR or expected value',
];
const CANNOT = [
  'Read news, the economic calendar or order books',
  'Search the internet or see live prices',
  'Predict prices beyond what the model supplied',
  'Place, change or close any trade',
];

/** Public, full-page research assistant (no sign-in): the rule-based demo on the simulated example setup. */
export function AssistantPublicPage() {
  useDocumentMeta({
    title: 'Research assistant',
    description: 'Ask about a simulated gold setup: its evidence, what would invalidate it and what it means for an example account. A rule-based demo that shows what every answer used.',
    path: '/ai-assistant',
  });
  const { source } = useServices();
  const s = buildShowcase();
  const o = s.opportunity;
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const p = (v: number) => formatPrice(v, inst.pricePrecision);

  return (
    <div className="violet-scene border-b border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] gap-10 px-5 pt-28 pb-16 sm:px-8 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] lg:pt-32">
        <div className="flex flex-col gap-6 lg:sticky lg:top-28 lg:self-start">
          <div>
            <p className="eyebrow mb-3">Research assistant</p>
            <RevealText
              as="h1"
              trigger="mount"
              className="display text-[2.5rem] leading-[1] text-fg sm:text-d2"
              lines={['Ask about the setup.', <em key="e">See what the answer used.</em>]}
            />
            <p className="m-in mt-4 text-md text-fg-2" style={{ '--at': '300ms' } as React.CSSProperties}>
              Question a simulated gold setup the way you would question your own research: what supports it, what would prove it wrong, and what it means for an
              account.
            </p>
          </div>

          <Reveal className="rounded-2xl border border-demo/40 bg-surface/90 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-fg">
              <FlaskConical aria-hidden className="size-4 text-demo" /> Rule-based demo — not a language model
            </p>
            <p className="mt-1.5 text-xs leading-5 text-fg-2">
              Every answer is assembled with fixed rules from the data listed under “Context”. No AI provider is connected and nothing you type leaves this browser.
            </p>
          </Reveal>

          <Reveal delay={80} className="rounded-2xl border border-line bg-surface/90 p-4">
            <div className="flex items-center gap-2">
              <p className="eyebrow">The example it answers about</p>
              <SourceTag kind="demo" className="ml-auto" />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <span className="font-semibold text-fg">{inst.display}</span>
              <span className="num text-xs text-fg-3">{SHOWCASE_TIMEFRAME}</span>
              <DirectionBadge direction={o.direction} />
              <span className="num ml-auto text-forecast">{formatPercent(o.probability)}</span>
            </div>
            <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-xs">
              <dt className="text-fg-3">Entry zone</dt>
              <dd className="num text-fg">
                {p(o.entryZone.low)} – {p(o.entryZone.high)}
              </dd>
              <dt className="text-fg-3">Stop zone</dt>
              <dd className="num text-fg">
                {p(o.stopLossZone.low)} – {p(o.stopLossZone.high)}
              </dd>
              <dt className="text-fg-3">Target zone</dt>
              <dd className="num text-fg">
                {p(o.takeProfitZone.low)} – {p(o.takeProfitZone.high)} · {formatRiskReward(o.riskReward)}
              </dd>
              <dt className="text-fg-3">Generated</dt>
              <dd className="num text-fg">{formatDateTime(o.generatedAt, 'UTC')} UTC (fixed example time)</dd>
            </dl>
          </Reveal>

          <Reveal delay={140} className="grid grid-cols-[minmax(0,1fr)] gap-4 text-sm sm:grid-cols-2 lg:grid-cols-1">
            <div>
              <p className="eyebrow mb-2">It can</p>
              <ul className="flex flex-col gap-1.5">
                {CAN.map((c) => (
                  <li key={c} className="flex gap-2 text-fg-2">
                    <Check aria-hidden className="mt-0.5 size-3.5 shrink-0 text-accent" /> {c}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="eyebrow mb-2">It cannot</p>
              <ul className="flex flex-col gap-1.5">
                {CANNOT.map((c) => (
                  <li key={c} className="flex gap-2 text-fg-2">
                    <Minus aria-hidden className="mt-0.5 size-3.5 shrink-0 text-fg-3" /> {c}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          {source === 'demo' && (
            <Link to="/assistant" viewTransition className="inline-flex items-center gap-1.5 text-sm text-fg-2 underline-offset-4 hover:text-fg hover:underline">
              Use it inside the app, on any instrument <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          )}
        </div>

        {/* The console */}
        <section aria-label="Research assistant" className="m-stage flex h-[min(780px,calc(100svh-120px))] min-h-[560px] flex-col overflow-hidden rounded-3xl border border-forecast/30 bg-surface shadow-float" style={{ '--at': '200ms' } as React.CSSProperties}>
          <PublicAssistant variant="page" />
        </section>
      </div>
    </div>
  );
}
