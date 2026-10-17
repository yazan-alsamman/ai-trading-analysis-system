import { ArrowRight, Check, Info, Minus } from 'lucide-react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { SideSheet } from '@/components/ui/SideSheet';
import { FEATURES, formatPrice, getPlan, type PlanId } from '@/domain/membership';
import { StatusBadge } from './PlanComponents';

/**
 * Plan-selection confirmation. Records the choice in the browser only and
 * explains, honestly, what happens next. There is no checkout and no payment.
 */
export function PlanConfirmSheet({ plan: id, onClose }: { plan: PlanId | null; onClose: () => void }) {
  const { source } = useServices();
  const plan = id ? getPlan(id) : null;
  const included = plan ? FEATURES.filter((f) => plan.access[f.id] !== false) : [];
  const excluded = plan ? FEATURES.filter((f) => plan.access[f.id] === false) : [];
  return (
    <SideSheet open={plan !== null} onClose={onClose} title="Your selection" width="lg">
      {plan && (
        <div className="flex h-full flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            <p className="eyebrow">Selected plan</p>
            <p className="display m-in mt-1 text-d2 text-fg">{plan.name}</p>
            <p className="mt-1 text-md text-fg-2">{plan.tagline}</p>
            <p className="mt-3 text-sm text-fg">{formatPrice(plan.price)}</p>

            <div className="mt-6 flex items-start gap-3 rounded-xl border border-dashed border-demo/50 bg-demo-soft p-4 text-sm text-fg-2">
              <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-demo" />
              <p>
                <strong className="font-semibold text-fg">Paid activation is not available yet.</strong> No billing service is connected, so nothing is charged and no
                subscription is created. Your choice is remembered in this browser so it can follow you through sign-up
                {source === 'demo' ? ', and you can preview the plan inside the app as a labelled demo membership.' : '.'}
              </p>
            </div>

            <ol className="mt-6 flex flex-col gap-3">
              {[
                ['Create an account or sign in', source === 'demo' ? 'In demo mode this creates a local demo session — nothing is sent to a server.' : 'With the project’s authentication service.'],
                ['Review your plan', 'See what is included and what each feature runs on today.'],
                ['Enter the platform', source === 'demo' ? 'Optionally preview the plan as a demo membership.' : 'Membership activation will follow once billing exists.'],
              ].map(([t, d], i) => (
                <li key={t} className="m-in flex gap-3" style={{ '--at': `${120 + i * 70}ms` } as React.CSSProperties}>
                  <span className="num inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-accent text-xs text-accent">{i + 1}</span>
                  <span>
                    <span className="block text-sm font-medium text-fg">{t}</span>
                    <span className="block text-xs text-fg-3">{d}</span>
                  </span>
                </li>
              ))}
            </ol>

            <div className="mt-8 grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-2">
              <div>
                <p className="eyebrow mb-2">Included</p>
                <ul className="flex flex-col gap-2">
                  {included.map((f) => (
                    <li key={f.id} className="flex items-start gap-2 text-sm">
                      <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
                      <span className="min-w-0">
                        <span className="text-fg">{f.label}</span>
                        {typeof plan.access[f.id] === 'string' && <span className="text-fg-3"> · {plan.access[f.id]}</span>}
                        <span className="mt-1 block">
                          <StatusBadge status={f.status} />
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              {excluded.length > 0 && (
                <div>
                  <p className="eyebrow mb-2">Not included</p>
                  <ul className="flex flex-col gap-2">
                    {excluded.map((f) => (
                      <li key={f.id} className="flex items-start gap-2 text-sm text-fg-3">
                        <Minus aria-hidden className="mt-0.5 size-4 shrink-0" />
                        {f.label}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-2 border-t border-line px-6 py-4 sm:flex-row">
            <Link to={`/register?plan=${plan.id}`} viewTransition className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill', className: 'flex-1' })}>
              Create account with {plan.name} <ArrowRight aria-hidden className="size-4" />
            </Link>
            <Link to={`/login?plan=${plan.id}`} viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'bg-transparent' })}>
              I have an account
            </Link>
          </div>
        </div>
      )}
    </SideSheet>
  );
}
