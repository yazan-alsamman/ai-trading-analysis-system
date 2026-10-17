import { ArrowUpRight, FlaskConical, LockKeyhole } from 'lucide-react';
import { Link } from 'react-router';
import { membershipStore, useDemoMembership } from '@/app/membershipStore';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { getFeature, getPlan, lowestPlanWith, type FeatureId } from '@/domain/membership';
import { cn } from '@/lib/cn';

export function PlanGate({ feature, className }: { feature: FeatureId; className?: string }) {
  const demo = useDemoMembership();
  const f = getFeature(feature);
  const needed = lowestPlanWith(feature);
  const current = demo ? getPlan(demo.plan) : null;
  return (
    <div role="region" aria-label={`${f.label} is not included in your demo plan`} className={cn('reveal mx-auto flex max-w-lg flex-col items-center px-6 py-16 text-center', className)}>
      <span className="inline-flex size-12 items-center justify-center rounded-full border border-line-strong text-accent">
        <LockKeyhole aria-hidden className="size-5" />
      </span>
      <p className="mt-4 flex items-center gap-2">
        <Badge tone="demo">
          <FlaskConical aria-hidden className="size-3" /> Demo plan: {current?.name}
        </Badge>
      </p>
      <h2 className="display mt-3 text-d3 text-fg">
        {f.label} <em>isn’t in {current?.name}.</em>
      </h2>
      <p className="mt-2 text-sm text-fg-2">
        {f.detail} It is included from <strong className="font-semibold text-fg">{needed?.name}</strong>. You are previewing plan-aware access in demo mode — this is not real
        access control and nothing has been purchased.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {needed && (
          <Button variant="primary" shape="pill" onClick={() => membershipStore.activateDemo(needed.id)}>
            Preview {needed.name} instead
          </Button>
        )}
        <Link to="/membership#compare" className={buttonClasses({ variant: 'secondary', shape: 'pill', className: 'bg-transparent' })}>
          Compare plans <ArrowUpRight aria-hidden className="size-4" />
        </Link>
        <Button variant="ghost" shape="pill" onClick={() => membershipStore.clearDemo()}>
          Exit plan preview
        </Button>
      </div>
    </div>
  );
}

/** Sidebar chip: the current demo plan, or nothing. */
export function DemoPlanChip({ collapsed }: { collapsed: boolean }) {
  const demo = useDemoMembership();
  if (!demo) return null;
  const plan = getPlan(demo.plan);
  return (
    <Link
      to="/settings#membership"
      title={`Demo plan preview: ${plan.name}. Not a subscription.`}
      className={cn(
        'flex items-center gap-2 rounded-md border border-dashed border-demo/50 bg-demo-soft text-xs text-fg-2 hover:text-fg',
        collapsed ? 'mx-auto size-8 justify-center' : 'px-2.5 py-1.5',
      )}
    >
      <FlaskConical aria-hidden className="size-3.5 shrink-0 text-demo" />
      {!collapsed && (
        <span className="truncate">
          Demo plan · <span className="font-medium text-fg">{plan.name}</span>
        </span>
      )}
      {collapsed && <span className="sr-only">Demo plan {plan.name}</span>}
    </Link>
  );
}
