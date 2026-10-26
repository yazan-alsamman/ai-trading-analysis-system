import { CloudOff, Inbox, OctagonAlert, PlugZap, RotateCw, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { isApiError, userMessage } from '@/services/errors';
import { Button } from './Button';

interface StateProps {
  title: string;
  description?: ReactNode;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

function StateView({ title, description, icon: Icon = Inbox, action, className, compact = false, tone = 'muted' }: StateProps & { tone?: 'muted' | 'danger' }) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center', compact ? 'gap-2 px-4 py-6' : 'gap-3 px-6 py-12', className)}>
      <Icon aria-hidden className={cn(compact ? 'size-5' : 'size-6', tone === 'danger' ? 'text-danger' : 'text-fg-3')} />
      <div className="max-w-sm">
        <p className="text-sm font-medium text-fg">{title}</p>
        {description && <p className="mt-1 text-sm text-fg-2">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState(props: StateProps) {
  return <StateView {...props} />;
}

/** Failure with plain-language reason and retry. Never an infinite spinner. */
export function ErrorState({ error, onRetry, title = 'Could not load data', compact, className }: { error: unknown; onRetry?: () => void; title?: string; compact?: boolean; className?: string }) {
  // A capability the backend does not offer is a deliberate state, not a failure: no alarm, no pointless retry.
  if (isApiError(error) && error.kind === 'not_available')
    return (
      <div role="status">
        <StateView icon={PlugZap} title="Not available yet" description={userMessage(error)} compact={compact ?? false} {...(className ? { className } : {})} />
      </div>
    );
  return (
    <div role="alert">
      <StateView
        tone="danger"
        icon={OctagonAlert}
        title={title}
        description={userMessage(error)}
        compact={compact ?? false}
        {...(className ? { className } : {})}
        action={
          onRetry && (
            <Button size="sm" icon={RotateCw} onClick={onRetry}>
              Try again
            </Button>
          )
        }
      />
    </div>
  );
}

export function OfflineState({ compact }: { compact?: boolean }) {
  return <StateView icon={CloudOff} title="You are offline" description="Reconnect to load this data. Nothing has been lost." compact={compact ?? false} />;
}

/** Shimmer-free skeleton block (respects reduced motion by not animating at all). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('rounded-sm bg-hover', className)} />;
}

/** Accessible loading wrapper: announces once, renders skeleton children. */
export function Loading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

export function SkeletonRows({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-row w-full" />
      ))}
    </div>
  );
}
