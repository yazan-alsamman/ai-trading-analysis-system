import { Check } from 'lucide-react';
import { Link } from 'react-router';
import { getPlan, type PlanId } from '@/domain/membership';
import { cn } from '@/lib/cn';

const STEPS = ['Plan', 'Account', 'Review & access'] as const;

/** Progress through the membership journey. `current` is 0-based. */
export function JourneySteps({ current }: { current: 0 | 1 | 2 }) {
  return (
    <nav aria-label="Sign-up progress">
      <ol className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const done = i < current;
          const now = i === current;
          return (
            <li key={s} className="flex items-center gap-2" aria-current={now ? 'step' : undefined}>
              <span
                className={cn(
                  'num inline-flex size-6 items-center justify-center rounded-full border text-xs transition-colors duration-300',
                  done ? 'border-accent bg-accent text-accent-fg' : now ? 'border-accent text-accent' : 'border-line-strong text-fg-3',
                )}
              >
                {done ? <Check aria-hidden className="size-3.5" /> : i + 1}
              </span>
              <span className={cn('text-xs whitespace-nowrap', now ? 'font-medium text-fg' : 'text-fg-3')}>
                {s}
                {done && <span className="sr-only"> (done)</span>}
              </span>
              {i < STEPS.length - 1 && <span aria-hidden className={cn('h-px w-6 sm:w-10', done ? 'bg-accent' : 'bg-line-strong')} />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Compact reminder of the selected plan, with a way back to compare. */
export function PlanSummary({ plan: id, className }: { plan: PlanId; className?: string }) {
  const plan = getPlan(id);
  return (
    <div className={cn('m-in rounded-xl border border-accent/50 bg-accent-soft p-4', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs text-fg-2">Selected plan</p>
        <Link to="/membership#plans" viewTransition className="text-xs font-medium text-fg underline-offset-4 hover:underline">
          Change plan
        </Link>
      </div>
      <p className="display mt-0.5 text-xl text-fg">{plan.name}</p>
      <p className="text-sm text-fg-2">{plan.tagline}</p>
      <ul className="mt-2 grid grid-cols-[minmax(0,1fr)] gap-1 text-xs text-fg-2 sm:grid-cols-2">
        {plan.highlights.slice(0, 4).map((h) => (
          <li key={h} className="flex gap-1.5">
            <Check aria-hidden className="mt-0.5 size-3 shrink-0 text-accent" />
            {h}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-fg-3">Pricing to be announced · no payment is taken.</p>
    </div>
  );
}
