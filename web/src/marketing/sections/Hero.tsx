import { ArrowDown, ArrowRight } from 'lucide-react';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { DirectionBadge } from '@/components/ui/Market';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { formatMoney, formatPct, formatPercent, formatProbabilityBand, formatRiskReward, formatUnits } from '@/lib/format';
import { RevealText } from '@/motion/Reveal';
import { useFinePointer, usePointerParallax, useReducedMotion } from '@/motion/runtime';
import { ShowcaseChart } from '../components/ShowcaseChart';
import { buildShowcase, SHOWCASE_PROFILE, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

const PRINCIPLES = ['Observed ≠ projected', 'Every number sourced', 'Risk sized to your limits', 'Never executes trades'];
const at = (ms: number) => ({ '--at': `${ms}ms` }) as CSSProperties;

/** Small glass card floating over the product stage. */
function StageCard({ children, className, delay, depth }: { children: React.ReactNode; className: string; delay: number; depth: number }) {
  return (
    <div className={`parallax ${className}`} style={{ '--depth': depth } as CSSProperties}>
      <div className="m-in rounded-2xl border border-line-strong bg-surface/85 p-4 shadow-float backdrop-blur-md" style={at(delay)}>
        {children}
      </div>
    </div>
  );
}

/**
 * Hero: editorial headline (line masks) → purpose → the market visual builds
 * itself (observed → NOW → model levels → projection) → product cards → CTAs.
 * Timed in CSS from first paint; pointer parallax on fine pointers only.
 */
export function Hero() {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const { source } = useServices();
  const reduced = useReducedMotion();
  const fine = useFinePointer();
  const stage = useRef<HTMLDivElement>(null);
  usePointerParallax(stage, fine && !reduced);

  // Pause the one ambient loop once the hero has scrolled away.
  const glow = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const el = glow.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => setVisible(!!e?.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const o = s.opportunity;
  const top = [...o.factors].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 2);

  return (
    <section aria-labelledby="hero-title" className="atmosphere relative overflow-hidden border-b border-line pt-28 pb-16 lg:min-h-[100svh] lg:pt-32">
      <div
        ref={glow}
        aria-hidden
        data-paused={!visible}
        className="atmos-drift pointer-events-none absolute -top-40 left-1/2 h-[720px] w-[1100px] -translate-x-1/2 rounded-full opacity-70"
        style={{ background: 'radial-gradient(closest-side, var(--atmos-aurum), transparent 70%)' }}
      />
      <div className="relative mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] items-center gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,600px)] lg:gap-10">
        <div className="flex flex-col gap-7">
          <p className="eyebrow m-in flex items-center gap-2" style={at(0)}>
            <span aria-hidden className="size-1.5 rounded-full bg-accent" />
            Gold &amp; FX research platform
          </p>
          <RevealText
            as="h1"
            id="hero-title"
            trigger="mount"
            delay={80}
            className="display text-[2.75rem] leading-[0.98] text-fg sm:text-d1 xl:text-[4.75rem]"
            lines={['Every gold idea,', 'researched, sized', <em key="em">and sourced.</em>]}
          />
          <p className="m-in-blur max-w-xl text-md text-fg-2 sm:text-[1.0625rem] sm:leading-7" style={at(520)}>
            See the chart, question the model and size the risk against your own limits — one workflow where every number says where it came from. Analysis only: it
            never trades for you.
          </p>
          <div className="m-in flex flex-wrap items-center gap-3" style={at(1100)}>
            <Link to="/membership#plans" viewTransition className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill' })}>
              Get started <ArrowRight aria-hidden className="size-4" />
            </Link>
            <a href="#platform" className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
              Explore the platform
            </a>
            {source === 'demo' && (
              <Link to="/overview" viewTransition className="px-2 text-sm text-fg-2 underline-offset-4 hover:text-fg hover:underline">
                or open the live demo →
              </Link>
            )}
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-5 text-xs text-fg-3">
            {PRINCIPLES.map((p, i) => (
              <li key={p} className="m-in flex items-center gap-2" style={at(1300 + i * 70)}>
                <span aria-hidden className="size-1 rounded-full bg-accent" />
                {p}
              </li>
            ))}
          </ul>
        </div>

        {/* Product stage */}
        <div ref={stage} className="relative">
          <div className="parallax" style={{ '--depth': 0.35 } as CSSProperties}>
            <figure className="m-stage overflow-hidden rounded-2xl border border-line-strong bg-surface/90 shadow-float" style={at(650)}>
              <div className="flex items-center gap-2 border-b border-line px-4 py-3">
                <span aria-hidden className="flex gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="size-2.5 rounded-full bg-line-strong" />
                  ))}
                </span>
                <span className="ml-2 text-sm font-semibold text-fg">{inst.display}</span>
                <span className="text-sm text-fg-3">· {SHOWCASE_TIMEFRAME}</span>
                <SourceTag kind="demo" className="ml-1" detail="Simulated demo data from the platform's fixtures — not a live market feed or the trained model." />
              </div>
              <div className="flex gap-x-4 gap-y-1 px-4 pt-3 text-xs text-fg-3">
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden className="h-0.5 w-4 rounded-full bg-accent" /> Observed (simulated)
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden className="w-4 border-t-2 border-dashed border-forecast" /> Model projection
                </span>
              </div>
              <div className="px-2 pt-3 pb-1">
                <ShowcaseChart
                  candles={s.candles}
                  opportunity={o}
                  timeframe={SHOWCASE_TIMEFRAME}
                  precision={inst.pricePrecision}
                  variant="line"
                  mode="intro"
                  label={`Simulated ${inst.display} ${SHOWCASE_TIMEFRAME} price history up to the NOW line, then the demo model's levels and its projected path, drawn dashed to the right of NOW.`}
                />
              </div>
              <div className="h-10 border-t border-line lg:h-14" aria-hidden />
            </figure>
          </div>

          {/* Floating evidence: model output, risk plan */}
          <StageCard className="mt-4 lg:absolute lg:-top-8 lg:-right-6 lg:mt-0 lg:w-56" delay={2700} depth={0.9}>
            <p className="eyebrow">Model output</p>
            <div className="mt-2 flex items-center gap-2">
              <DirectionBadge direction={o.direction} />
              <span className="num text-xl text-forecast">{formatPercent(o.probability)}</span>
            </div>
            <p className="mt-1 text-xs text-fg-3">probability the target is reached before the stop · band {formatProbabilityBand(o.confidenceBand)}</p>
          </StageCard>
          <StageCard className="mt-3 lg:absolute lg:-bottom-10 lg:-left-10 lg:mt-0 lg:w-64" delay={2850} depth={1}>
            <p className="eyebrow">Risk plan</p>
            <p className="mt-0.5 text-xs text-fg-3">Example: {formatMoney(SHOWCASE_PROFILE.capital, 'USD').replace('.00', '')} at 1 %</p>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
              <dt className="text-fg-3">Position</dt>
              <dd className="num text-right text-fg">{formatUnits(s.risk.units, inst.base)}</dd>
              <dt className="text-fg-3">At risk</dt>
              <dd className="num text-right text-down">{formatMoney(s.risk.monetaryRisk, 'USD')}</dd>
              <dt className="text-fg-3">Reward : risk</dt>
              <dd className="num text-right text-fg">{formatRiskReward(s.risk.riskReward)}</dd>
              <dt className="text-fg-3">Of capital</dt>
              <dd className="num text-right text-fg">{formatPct(s.risk.riskPctOfCapital)}</dd>
            </dl>
          </StageCard>
          <StageCard className="mt-3 lg:absolute lg:right-2 lg:-bottom-16 lg:mt-0 lg:w-60" delay={3000} depth={0.7}>
            <p className="eyebrow">Evidence</p>
            <ul className="mt-2 flex flex-col gap-1 text-xs text-fg-2">
              {top.map((f) => (
                <li key={f.id} className="flex justify-between gap-2">
                  <span className="truncate">{f.label}</span>
                  <span className="num text-fg-3">
                    {f.contribution >= 0 ? '+' : '−'}
                    {Math.abs(f.contribution).toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          </StageCard>
        </div>
      </div>
      <a href="#problem" className="m-fade relative mx-auto mt-24 hidden w-max items-center gap-2 text-xs text-fg-3 hover:text-fg lg:flex" style={at(3200)}>
        <ArrowDown aria-hidden className="size-3.5" /> Why it exists
      </a>
    </section>
  );
}
