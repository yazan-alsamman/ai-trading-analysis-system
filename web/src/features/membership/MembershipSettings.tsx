import { ArrowUpRight, FlaskConical } from 'lucide-react';
import { Link } from 'react-router';
import { membershipStore, useDemoMembership } from '@/app/membershipStore';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Panel';
import { PLANS } from '@/domain/membership';
import { cn } from '@/lib/cn';

/** Settings → Membership: the labelled DEMO plan preview (no billing exists). */
export function MembershipSettings() {
  const demo = useDemoMembership();
  return (
    <div id="membership" className="scroll-mt-4">
      <Panel
        title="Membership"
        meta={
          <Badge tone="demo">
            <FlaskConical aria-hidden className="size-3" /> Demo preview
          </Badge>
        }
        actions={
          <Link to="/membership#compare" className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
            Compare plans <ArrowUpRight aria-hidden className="size-3.5" />
          </Link>
        }
      >
        <p className="text-sm text-fg-2">
          Subscriptions are not available yet — no billing service is connected. You can preview how a plan shapes the app. The preview is stored in this browser and is not
          access control.
        </p>
        <div role="radiogroup" aria-label="Demo plan preview" className="mt-4 grid gap-2 sm:grid-cols-4">
          <button
            type="button"
            role="radio"
            aria-checked={!demo}
            onClick={() => membershipStore.clearDemo()}
            className={cn('rounded-lg border px-3 py-2.5 text-left text-sm transition-colors', !demo ? 'border-accent bg-accent-soft text-fg' : 'border-line text-fg-2 hover:bg-hover')}
          >
            <span className="block font-medium">No preview</span>
            <span className="block text-xs text-fg-3">Every module open</span>
          </button>
          {PLANS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={demo?.plan === p.id}
              onClick={() => membershipStore.activateDemo(p.id)}
              className={cn(
                'rounded-lg border px-3 py-2.5 text-left text-sm transition-colors',
                demo?.plan === p.id ? 'border-accent bg-accent-soft text-fg' : 'border-line text-fg-2 hover:bg-hover',
              )}
            >
              <span className="block font-medium">{p.name}</span>
              <span className="block truncate text-xs text-fg-3">{p.tagline}</span>
            </button>
          ))}
        </div>
        {demo && (
          <div className="mt-3">
            <Button size="sm" variant="ghost" onClick={() => membershipStore.clearDemo()}>
              Exit plan preview
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}
