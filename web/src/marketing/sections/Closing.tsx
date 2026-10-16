import { ArrowRight, Plus } from 'lucide-react';
import { useId, useState } from 'react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { cn } from '@/lib/cn';
import { Reveal, RevealText } from '@/motion/Reveal';
import type { FaqItem } from '../content';

/** Accessible accordion (buttons + aria-expanded), animated with grid rows. */
export function Faq({ items, title = 'Questions, answered plainly.', eyebrow = '08 · FAQ', id = 'faq' }: { items: FaqItem[]; title?: string; eyebrow?: string; id?: string }) {
  const [open, setOpen] = useState<number | null>(0);
  const base = useId();
  return (
    <section id={id} data-section aria-labelledby={`${base}-title`} className="border-b border-line">
      <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-10 px-5 py-24 sm:px-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div>
          <p className="eyebrow mb-3">{eyebrow}</p>
          <RevealText as="h2" id={`${base}-title`} className="display text-d3 text-fg sm:text-d2" lines={title.split('. ').map((l, i, a) => (i < a.length - 1 ? `${l}.` : l))} />
        </div>
        <ul className="flex flex-col divide-y divide-line border-y border-line">
          {items.map((item, i) => {
            const isOpen = open === i;
            return (
              <Reveal as="li" key={item.q} index={i} stagger={50}>
                <h3>
                  <button
                    type="button"
                    id={`${base}-q${i}`}
                    aria-expanded={isOpen}
                    aria-controls={`${base}-a${i}`}
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="flex w-full items-center justify-between gap-4 py-5 text-left text-md font-medium text-fg hover:text-accent"
                  >
                    {item.q}
                    <Plus aria-hidden className={cn('size-5 shrink-0 text-fg-3 transition-transform duration-[260ms] ease-[var(--m-ease-out)]', isOpen && 'rotate-45 text-accent')} />
                  </button>
                </h3>
                <div id={`${base}-a${i}`} role="region" aria-labelledby={`${base}-q${i}`} className="accordion-panel" data-open={isOpen} inert={!isOpen}>
                  <div>
                    <p className="max-w-2xl pb-5 text-sm leading-6 text-fg-2">{item.a}</p>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

export function FinalCta() {
  const { source } = useServices();
  return (
    <section aria-labelledby="final-title" className="atmosphere relative overflow-hidden border-b border-line">
      <div className="relative mx-auto flex max-w-[1240px] flex-col items-center px-5 py-28 text-center sm:px-8">
        <p className="eyebrow mb-4">Next step</p>
        <RevealText as="h2" id="final-title" className="display text-d2 text-fg sm:text-d1" lines={['Start with', <em key="e">the evidence.</em>]} />
        <Reveal as="p" delay={180} className="mt-5 max-w-xl text-md text-fg-2">
          Compare the plans, create an account, or open the live demo and try the whole workflow on simulated data — no sign-in needed.
        </Reveal>
        <Reveal delay={300} className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to="/membership#plans" viewTransition className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill' })}>
            Compare plans <ArrowRight aria-hidden className="size-4" />
          </Link>
          {source === 'demo' ? (
            <Link to="/overview" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
              Open the live demo
            </Link>
          ) : (
            <Link to="/login" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
              Sign in
            </Link>
          )}
        </Reveal>
      </div>
    </section>
  );
}
