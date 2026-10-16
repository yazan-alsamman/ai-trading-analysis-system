import { Check, X } from 'lucide-react';
import { useLayoutEffect, useRef } from 'react';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useCinematic, useScrollProgress } from '@/motion/runtime';
import { easeInOut, lerp, segment } from '@/motion/tokens';

/** Each fragment of unstructured research resolves into one module of the workflow. */
const FRAGMENTS = [
  { messy: 'Three tabs that disagree', clean: 'Market intelligence', x: 0.52, y: 0.06, r: -6 },
  { messy: 'A screenshot of a chart', clean: 'Chart analysis', x: 0.06, y: 0.2, r: 5 },
  { messy: '“92% sure” — says who?', clean: 'AI research, with evidence', x: 0.6, y: 0.34, r: 4 },
  { messy: 'Position size: a guess', clean: 'Risk sized to your capital', x: 0.14, y: 0.5, r: -7 },
  { messy: 'A tip from a chat group', clean: 'Personalised signals', x: 0.5, y: 0.64, r: -3 },
  { messy: 'Was it right last time?', clean: 'Performance insights', x: 0.02, y: 0.78, r: 6 },
  { messy: 'No one to ask why', clean: 'Assistant on the evidence', x: 0.46, y: 0.88, r: -5 },
];

const ROW = 62;

function StaticVersion() {
  return (
    <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-10 px-5 py-24 sm:px-8 lg:grid-cols-2">
      <div>
        <p className="eyebrow mb-3">01 · The problem</p>
        <RevealText as="h2" className="display text-d3 text-fg sm:text-d2" lines={['Too many inputs.', <em key="e">No structure.</em>]} />
        <Reveal as="p" delay={120} className="mt-4 max-w-xl text-md text-fg-2">
          A tip in a chat group, three tabs that disagree, a model score with no explanation, a position size guessed at the last minute. Most trading research is a pile of
          fragments.
        </Reveal>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-2">
        <ul aria-label="Before" className="flex flex-col gap-2">
          {FRAGMENTS.map((f, i) => (
            <Reveal as="li" key={f.messy} index={i} className="flex items-center gap-2 rounded-lg border border-dashed border-line-strong px-3 py-2 text-sm text-fg-3">
              <X aria-hidden className="size-3.5 shrink-0 text-down" /> {f.messy}
            </Reveal>
          ))}
        </ul>
        <ul aria-label="With the platform" className="flex flex-col gap-2">
          {FRAGMENTS.map((f, i) => (
            <Reveal as="li" key={f.clean} index={i + 2} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg">
              <Check aria-hidden className="size-3.5 shrink-0 text-accent" />
              <span className="num text-xs text-fg-3">0{i + 1}</span> {f.clean}
            </Reveal>
          ))}
        </ul>
      </div>
    </div>
  );
}

/**
 * Sequence A — pinned on wide screens: scattered fragments travel into an
 * ordered workflow as the visitor scrolls (transform/opacity only, written
 * directly to the DOM each frame). Static two-column version otherwise.
 */
export function ProblemSequence() {
  const cinematic = useCinematic();
  const outer = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLLIElement | null)[]>([]);
  const before = useRef<HTMLDivElement>(null);
  const after = useRef<HTMLDivElement>(null);
  const spine = useRef<HTMLSpanElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const size = useRef({ w: 0, h: 0 });

  useLayoutEffect(() => {
    const el = stage.current;
    if (!el || !cinematic) return;
    const measure = () => (size.current = { w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [cinematic]);

  useScrollProgress(
    outer,
    (p) => {
      const { w, h } = size.current;
      FRAGMENTS.forEach((f, i) => {
        const el = items.current[i];
        if (!el) return;
        const t = easeInOut(segment(p, 0.16 + i * 0.035, 0.58 + i * 0.035));
        const dx = lerp(f.x * w, 0, t);
        const dy = lerp(f.y * (h - 40), i * ROW, t);
        el.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0) rotate(${lerp(f.r, 0, t).toFixed(2)}deg)`;
        el.style.setProperty('--t', t.toFixed(3));
        el.dataset.ordered = String(t > 0.98);
      });
      // Sequential (never overlapping) swap of the two headlines.
      const out = segment(p, 0.34, 0.44);
      const inn = segment(p, 0.46, 0.56);
      if (before.current) {
        before.current.style.opacity = String(1 - out);
        before.current.style.transform = `translate3d(0, ${(-14 * out).toFixed(1)}px, 0)`;
        before.current.style.visibility = out >= 1 ? 'hidden' : 'visible';
      }
      if (after.current) {
        after.current.style.opacity = String(inn);
        after.current.style.transform = `translate3d(0, ${(14 * (1 - inn)).toFixed(1)}px, 0)`;
        after.current.style.visibility = inn <= 0 ? 'hidden' : 'visible';
      }
      if (spine.current) spine.current.style.transform = `scaleY(${segment(p, 0.62, 0.9).toFixed(3)})`;
      if (bar.current) bar.current.style.transform = `scaleX(${p.toFixed(3)})`;
    },
    cinematic,
  );

  if (!cinematic) {
    return (
      <section id="problem" data-section aria-labelledby="problem-title" className="border-b border-line">
        <h2 id="problem-title" className="sr-only">
          From information overload to structured research
        </h2>
        <StaticVersion />
      </section>
    );
  }

  return (
    <section id="problem" data-section ref={outer} aria-labelledby="problem-title" className="relative h-[230vh] border-b border-line">
      <h2 id="problem-title" className="sr-only">
        From information overload to structured research
      </h2>
      <div className="sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <div className="mx-auto grid grid-cols-[minmax(0,1fr)] w-full max-w-[1240px] items-center gap-12 px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)]">
          <div className="relative min-h-[300px]">
            <p className="eyebrow mb-3">01 · The problem</p>
            <div ref={before} className="absolute inset-x-0 top-8">
              <p className="display text-d2 text-fg">
                Too many inputs. <em>No structure.</em>
              </p>
              <p className="mt-4 max-w-lg text-md text-fg-2">
                A tip in a chat group, three tabs that disagree, a model score with no explanation, a position size guessed at the last minute. Most trading research is a
                pile of fragments.
              </p>
            </div>
            <div ref={after} className="absolute inset-x-0 top-8 opacity-0">
              <p className="display text-d2 text-fg">
                One workflow. <em>Every input in its place.</em>
              </p>
              <p className="mt-4 max-w-lg text-md text-fg-2">
                The platform puts each fragment where it belongs — context, chart, model, evidence, risk, review — and labels where every number came from.
              </p>
            </div>
          </div>

          <div ref={stage} className="relative h-[460px]">
            <span ref={spine} aria-hidden className="absolute top-4 bottom-10 left-[19px] w-px origin-top scale-y-0 bg-accent/60" />
            <ol aria-label="Fragments of unstructured research and the module that replaces each">
              {FRAGMENTS.map((f, i) => (
                <li
                  key={f.messy}
                  ref={(n) => {
                    items.current[i] = n;
                  }}
                  className="fragment absolute top-0 left-0 flex items-center gap-3 will-change-transform"
                >
                  <span className="fragment-num num relative z-[1] inline-flex size-10 shrink-0 items-center justify-center rounded-full border text-xs">0{i + 1}</span>
                  <span className="fragment-label grid rounded-full border px-4 py-2 text-sm whitespace-nowrap">
                    <span className="fragment-messy col-start-1 row-start-1">{f.messy}</span>
                    <span className="fragment-clean col-start-1 row-start-1 font-medium">{f.clean}</span>
                  </span>
                </li>
              ))}
            </ol>
            <span aria-hidden className="absolute right-0 bottom-0 left-0 h-px overflow-hidden bg-line">
              <span ref={bar} className="block h-full origin-left scale-x-0 bg-accent" />
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
