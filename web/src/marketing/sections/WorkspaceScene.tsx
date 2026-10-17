import { CircleCheck, Scale, Sparkles } from 'lucide-react';
import { useLayoutEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { getInstrument } from '@/domain/instruments';
import { formatMoney, formatPct, formatPercent } from '@/lib/format';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useCinematic, useScrollProgress } from '@/motion/runtime';
import { easeInOut, easeOut, lerp, segment } from '@/motion/tokens';
import { WorkspaceScreen } from '../components/WorkspaceScreen';
import { buildShowcase, SHOWCASE_SYMBOL } from '../showcase';

function Panel({ icon, title, children, className, panelRef, depth }: { icon: ReactNode; title: string; children: ReactNode; className?: string; panelRef?: (n: HTMLDivElement | null) => void; depth: number }) {
  return (
    <div
      ref={panelRef}
      className={`depth-panel w-52 rounded-xl border border-line-strong bg-surface p-3 shadow-float ${className ?? ''}`}
      style={{ '--z': `${depth}px` } as CSSProperties}
    >
      <p className="flex items-center gap-1.5 text-xs text-fg-3">
        {icon} {title}
      </p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

/**
 * Scene: the workspace. A CSS-3D laptop (lid, screen, keyboard deck) shows the
 * actual research workspace UI built from the app's components. On wide
 * screens the scroll position opens the lid, turns the machine slowly and
 * brings three panels forward in depth; elsewhere it is a still, open laptop.
 * Only transforms and opacity change — no WebGL, no canvas.
 */
export function WorkspaceScene() {
  const cinematic = useCinematic();
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const outer = useRef<HTMLElement>(null);
  const laptop = useRef<HTMLDivElement>(null);
  const screen = useRef<HTMLDivElement>(null);
  const panels = useRef<(HTMLDivElement | null)[]>([]);

  // Scale the 1000 × 625 screen UI to whatever size the laptop is drawn at.
  useLayoutEffect(() => {
    const el = screen.current;
    if (!el) return;
    const fit = () => el.style.setProperty('--s', (el.clientWidth / 1000).toFixed(4));
    fit();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useScrollProgress(
    outer,
    (p) => {
      const el = laptop.current;
      if (!el) return;
      const open = easeOut(segment(p, 0.04, 0.4));
      const turn = easeInOut(segment(p, 0.36, 1));
      // Closed: seen from above and raised into view; open: the working angle.
      el.style.setProperty('--lid', `${lerp(-82, 4, open).toFixed(2)}deg`);
      el.style.setProperty('--rx', `${lerp(-40, -9, open).toFixed(2)}deg`);
      el.style.setProperty('--ry', `${(lerp(-22, -10, open) + turn * 20).toFixed(2)}deg`);
      el.style.setProperty('--lift', `${lerp(-170, 0, open).toFixed(1)}px`);
      panels.current.forEach((n, i) => {
        if (!n) return;
        const k = easeOut(segment(p, 0.42 + i * 0.09, 0.58 + i * 0.09));
        n.style.opacity = k.toFixed(3);
        n.style.setProperty('--z', `${(lerp(0, 90 + i * 35, k)).toFixed(1)}px`);
      });
    },
    cinematic,
  );

  const checksPassed = s.evaluation.checks.filter((c) => c.status === 'pass').length;
  const device = (
    <div className="laptop-scene mx-auto w-full" aria-hidden>
      <div ref={laptop} className="laptop mx-auto w-[min(860px,100%)]" data-testid="laptop">
        <div className="laptop-lid">
          <div ref={screen} className="laptop-screen">
            <WorkspaceScreen />
          </div>
          <div className="laptop-cover" />
        </div>
        <div className="laptop-deck" />
        <div className="laptop-shadow" />
        {cinematic && (
          <>
            <Panel
              panelRef={(n) => {
                panels.current[0] = n;
              }}
              icon={<Sparkles className="size-3.5 text-forecast" />}
              title="Model output"
              className="absolute top-[10%] -left-[9%] opacity-0"
              depth={0}
            >
              <p className="num text-lg text-forecast">
                {formatPercent(s.opportunity.probability)} <span className="text-sm text-fg-2">{s.opportunity.direction}</span>
              </p>
            </Panel>
            <Panel
              panelRef={(n) => {
                panels.current[1] = n;
              }}
              icon={<Scale className="size-3.5 text-accent" />}
              title="Loss at the stop"
              className="absolute top-[34%] -right-[8%] opacity-0"
              depth={0}
            >
              <p className="num text-lg text-down">{formatMoney(s.risk.monetaryRisk, 'USD')}</p>
              <p className="text-xs text-fg-3">{formatPct(s.risk.riskPctOfCapital)} of $25,000</p>
            </Panel>
            <Panel
              panelRef={(n) => {
                panels.current[2] = n;
              }}
              icon={<CircleCheck className="size-3.5 text-accent" />}
              title="Your checks"
              className="absolute top-[66%] -left-[6%] opacity-0"
              depth={0}
            >
              <p className="text-sm text-fg">
                <span className="num">{checksPassed}</span> of <span className="num">{s.evaluation.checks.length}</span> pass
              </p>
            </Panel>
          </>
        )}
      </div>
    </div>
  );

  const intro = (
    <div className="mx-auto max-w-3xl text-center">
      <p className="eyebrow mb-3">02 · The workspace</p>
      <RevealText as="h2" id="workspace-title" className="display text-d3 text-fg sm:text-d2" lines={['Close the tabs.', <em key="e">Open one desk.</em>]} />
      <Reveal as="p" delay={150} className="mx-auto mt-4 max-w-xl text-md text-fg-2">
        Chart, model output, evidence and risk side by side — the actual research workspace, shown with simulated demo data.
      </Reveal>
    </div>
  );
  const description = (
    <p className="sr-only">
      Illustration: the research workspace on a laptop. It shows simulated {inst.display} candles with the demo model’s levels, its output (
      {formatPercent(s.opportunity.probability)}, {s.opportunity.direction}), the strongest evidence and a risk plan losing {formatMoney(s.risk.monetaryRisk, 'USD')} at the
      stop on an example $25,000 account.
    </p>
  );

  if (!cinematic) {
    return (
      <section id="workspace" data-section aria-labelledby="workspace-title" className="overflow-hidden border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 pt-24 pb-28 sm:px-8">
          {intro}
          {description}
          <Reveal variant="scale" className="mt-12 px-2 sm:px-10">
            {device}
          </Reveal>
        </div>
      </section>
    );
  }

  return (
    <section ref={outer} id="workspace" data-section aria-labelledby="workspace-title" className="relative h-[260vh] border-b border-line">
      <div className="sticky top-0 flex h-[100svh] flex-col justify-center gap-8 overflow-hidden px-8 pt-16">
        {intro}
        {description}
        <div className="mx-auto w-[min(820px,58vw,calc((100svh-340px)*1.2))]">{device}</div>
      </div>
    </section>
  );
}
