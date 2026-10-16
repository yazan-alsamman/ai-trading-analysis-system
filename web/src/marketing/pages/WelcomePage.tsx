import { ArrowRight, Check, FlaskConical, Info, Minus } from 'lucide-react';
import { Link, Navigate, useNavigate } from 'react-router';
import { useAuth, useServices } from '@/app/contexts';
import { membershipStore } from '@/app/membershipStore';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { FEATURES, getPlan } from '@/domain/membership';
import { usePageTitle } from '@/hooks/usePageTitle';
import { StatusBadge } from '../membership/PlanComponents';
import { JourneySteps } from '../membership/Journey';
import { useJourneyPlan } from '../membership/useJourneyPlan';

/**
 * Step 3 of the journey: review the selected plan and enter the platform.
 * It stops at the honest boundary — there is no billing, so nothing is
 * activated. In demo mode the plan can be previewed as a labelled demo state.
 */
export function WelcomePage() {
  usePageTitle('Review your plan');
  const { session } = useAuth();
  const { source } = useServices();
  const navigate = useNavigate();
  const planId = useJourneyPlan();
  const plan = planId ? getPlan(planId) : null;
  const name = session?.user.name.split(' ')[0];

  // With a real backend, this step needs a signed-in account.
  if (source === 'api' && !session) return <Navigate to={planId ? `/login?plan=${planId}` : '/login'} replace />;

  const enter = (preview: boolean) => {
    if (preview && planId) membershipStore.activateDemo(planId);
    navigate('/overview', { viewTransition: true });
  };

  return (
    <div className="reveal flex flex-col gap-7" style={{ viewTransitionName: 'auth-card' }}>
      <JourneySteps current={2} />
      <div>
        <h1 className="display text-d3 text-fg sm:text-d2">
          {name ? `Welcome, ${name}.` : 'Welcome.'} <em>{plan ? 'Review your plan.' : 'Choose how to start.'}</em>
        </h1>
        <p className="mt-2 text-sm text-fg-2">{session?.isDemo || !session ? 'You are using a demo session.' : 'You are signed in.'}</p>
      </div>

      {plan ? (
        <>
          <div className="rounded-xl border border-line-strong bg-surface p-5">
            <div className="flex items-baseline justify-between">
              <p className="display text-xl text-fg">{plan.name}</p>
              <Link to="/membership#compare" viewTransition className="text-xs font-medium text-fg-2 underline-offset-4 hover:text-fg hover:underline">
                Compare plans
              </Link>
            </div>
            <p className="text-sm text-fg-2">{plan.tagline}</p>
            <ul className="mt-4 flex max-h-56 flex-col gap-2 overflow-y-auto pr-1">
              {FEATURES.map((f) => {
                const a = plan.access[f.id];
                return (
                  <li key={f.id} className="flex items-center gap-2 text-sm">
                    {a === false ? <Minus aria-hidden className="size-4 shrink-0 text-fg-3" /> : <Check aria-hidden className="size-4 shrink-0 text-accent" />}
                    <span className={a === false ? 'text-fg-3' : 'text-fg'}>
                      {f.label}
                      {typeof a === 'string' && <span className="text-fg-3"> · {a}</span>}
                      {a === false && <span className="sr-only"> (not included)</span>}
                    </span>
                    {a !== false && (
                      <span className="ml-auto">
                        <StatusBadge status={f.status} />
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="flex items-start gap-3 rounded-xl border border-dashed border-demo/50 bg-demo-soft p-4 text-sm text-fg-2">
            <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-demo" />
            <p>
              <strong className="font-semibold text-fg">Activation isn’t available yet.</strong> No billing service is connected, so this plan cannot be purchased or activated.
              {source === 'demo'
                ? ' You can preview it as a demo membership: the app will show which modules the plan includes. It is a preview, not access control.'
                : ' Your account currently has the platform’s standard access.'}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            {source === 'demo' && (
              <Button variant="primary" size="lg" shape="pill" icon={FlaskConical} onClick={() => enter(true)} className="w-full">
                Preview {plan.name} as a demo
              </Button>
            )}
            <Button variant={source === 'demo' ? 'secondary' : 'primary'} size="lg" shape="pill" trailingIcon={ArrowRight} onClick={() => enter(false)} className="w-full">
              Enter the platform{source === 'demo' ? ' without a plan preview' : ''}
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-fg-2">You haven’t chosen a plan. You can explore everything in the demo, or compare plans first.</p>
          <Link to="/membership#plans" viewTransition className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'w-full bg-transparent' })}>
            Compare plans
          </Link>
          <Button variant="primary" size="lg" shape="pill" trailingIcon={ArrowRight} onClick={() => enter(false)} className="w-full">
            Enter the platform
          </Button>
        </div>
      )}
    </div>
  );
}
