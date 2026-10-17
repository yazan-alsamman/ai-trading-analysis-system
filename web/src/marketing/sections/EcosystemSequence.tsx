import { useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { MODULES } from '@/layouts/navigation';
import { cn } from '@/lib/cn';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useCinematic, useReducedMotion, useStepProgress } from '@/motion/runtime';
import { MODULE_PREVIEWS } from '../components/ModulePreviews';

const COUNT = MODULES.length;

/**
 * Sequence B — the seven modules as one workflow. Pinned on wide screens:
 * scroll progress selects the module, fills the rail, moves the connector
 * marker and swaps the preview. Always a real tablist (click / arrow keys).
 */
export function EcosystemSequence() {
  const cinematic = useCinematic();
  const reduced = useReducedMotion();
  const outer = useRef<HTMLDivElement>(null);
  const scrolled = useStepProgress(outer, COUNT, cinematic);
  const [picked, setPicked] = useState(0);
  const active = cinematic ? scrolled : picked;
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  // Where the data packet travels from/to (adjusted during render when the module changes).
  const [trail, setTrail] = useState({ from: active, to: active });
  if (trail.to !== active) setTrail({ from: trail.to, to: active });

  const select = (i: number) => {
    if (cinematic && outer.current) {
      // Scroll to the middle of that step's range — the scroll position stays the single source of truth.
      const el = outer.current;
      const top = el.getBoundingClientRect().top + window.scrollY;
      const distance = el.offsetHeight - window.innerHeight;
      window.scrollTo({ top: top + ((i + 0.5) / COUNT) * distance, behavior: reduced ? 'auto' : 'smooth' });
    } else setPicked(i);
  };
  const onKey = (e: KeyboardEvent, i: number) => {
    const d = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = (i + d + COUNT) % COUNT;
    select(next);
    tabs.current[next]?.focus();
  };

  const body = (
    <div className="mx-auto grid grid-cols-[minmax(0,1fr)] w-full max-w-[1240px] gap-8 px-5 sm:px-8 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] lg:gap-14">
      {/* Module rail */}
      <div className="relative">
        <span aria-hidden className="absolute top-3 bottom-3 left-[19px] hidden w-px bg-line lg:block">
          <span className="block h-full origin-top bg-accent" style={{ transform: cinematic ? 'scaleY(var(--p, 0))' : `scaleY(${(active + 1) / COUNT})` }} />
        </span>
        <div role="tablist" aria-label="Platform modules" aria-orientation="vertical" className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0">
          {MODULES.map((m, i) => {
            const on = i === active;
            return (
              <button
                key={m.n}
                ref={(n) => {
                  tabs.current[i] = n;
                }}
                type="button"
                role="tab"
                id={`module-tab-${i}`}
                aria-selected={on}
                aria-controls={`module-panel-${i}`}
                tabIndex={on ? 0 : -1}
                onClick={() => select(i)}
                onKeyDown={(e) => onKey(e, i)}
                className={cn(
                  'group relative flex shrink-0 items-start gap-3 rounded-xl px-0 py-2 text-left transition-colors duration-200 lg:px-0 lg:py-2.5',
                  'max-lg:rounded-full max-lg:border max-lg:px-3.5 max-lg:py-1.5',
                  on ? 'max-lg:border-accent max-lg:bg-accent-soft' : 'max-lg:border-line',
                )}
              >
                <span
                  className={cn(
                    'num relative z-[1] hidden size-10 shrink-0 items-center justify-center rounded-full border text-xs transition-colors duration-200 lg:inline-flex',
                    on ? 'border-accent bg-canvas text-accent' : 'border-line-strong bg-canvas text-fg-3',
                  )}
                >
                  {m.n}
                </span>
                <span className="min-w-0 lg:pt-1">
                  <span className={cn('block text-sm font-medium transition-colors whitespace-nowrap lg:text-md', on ? 'text-fg' : 'text-fg-2 group-hover:text-fg')}>{m.name}</span>
                  <span
                    className={cn(
                      'display hidden overflow-hidden text-lg italic transition-[max-height,opacity] duration-300 lg:block',
                      on ? 'max-h-10 text-fg-2 opacity-100' : 'max-h-0 opacity-0',
                    )}
                  >
                    {m.question}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Connector + preview */}
      <div className="flex min-w-0 flex-col gap-5">
        <div aria-hidden className="relative hidden h-6 overflow-hidden md:block">
          <span className="absolute top-1/2 right-3 left-3 h-px bg-line" />
          <span className="absolute top-1/2 left-3 h-px origin-left bg-accent transition-transform duration-500 ease-[var(--m-ease-out)]" style={{ right: '0.75rem', transform: `scaleX(${active / (COUNT - 1)})` }} />
          {MODULES.map((m, i) => (
            <span
              key={m.n}
              className={cn('absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border transition-colors duration-300', i <= active ? 'border-accent bg-accent' : 'border-line-strong bg-canvas')}
              style={{ left: `calc(0.75rem + (100% - 1.5rem) * ${i / (COUNT - 1)})` }}
            />
          ))}
          <span
            className="absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/60 transition-[left] duration-500 ease-[var(--m-ease-out)]"
            style={{ left: `calc(0.75rem + (100% - 1.5rem) * ${active / (COUNT - 1)})` }}
          />
          {/* A data packet carries the previous module's result to the next one. */}
          {trail.from !== trail.to && (
            <span
              key={`${trail.from}-${trail.to}`}
              className="packet-track absolute top-1/2 right-3 left-3 h-0"
              style={{ '--from': trail.from / (COUNT - 1), '--to': trail.to / (COUNT - 1) } as CSSProperties}
            >
              <span className="absolute -top-[3px] left-0 h-1.5 w-6 -translate-x-1/2 rounded-full bg-accent shadow-[0_0_14px_var(--accent)]" />
            </span>
          )}
        </div>
        <div className="relative h-[440px] sm:h-[460px]">
          {MODULE_PREVIEWS.map((Preview, i) => (
            <div
              key={i}
              role="tabpanel"
              id={`module-panel-${i}`}
              aria-labelledby={`module-tab-${i}`}
              hidden={i !== active && !cinematic}
              data-layer
              data-on={i === active}
              aria-hidden={i !== active}
              className={cn('absolute inset-0', i !== active && 'pointer-events-none')}
              style={{ '--layer-delay': i === active ? '80ms' : '0ms' } as CSSProperties}
            >
              <Preview />
            </div>
          ))}
        </div>
        <p className="text-sm text-fg-2">
          <span className="num mr-2 text-fg-3">{MODULES[active]?.n}</span>
          {MODULES[active]?.summary}
        </p>
      </div>
    </div>
  );

  return (
    <section id="platform" data-section aria-labelledby="platform-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 pt-24 pb-10 sm:px-8">
        <p className="eyebrow mb-3">03 · The platform</p>
        <RevealText as="h2" id="platform-title" className="display text-d3 text-fg sm:text-d2" lines={['Seven modules.', <em key="e">One research workflow.</em>]} />
        <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
          Each module answers one question on the way from market noise to a decision you can justify — and hands its result to the next.
        </Reveal>
      </div>
      {cinematic ? (
        <div ref={outer} className="relative h-[340vh]">
          <div className="sticky top-0 flex h-[100svh] items-center">{body}</div>
        </div>
      ) : (
        <div className="pb-24">{body}</div>
      )}
    </section>
  );
}
