import { FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type BadgeTone = 'neutral' | 'accent' | 'up' | 'down' | 'forecast' | 'warning' | 'danger' | 'info' | 'demo';

const TONE: Record<BadgeTone, string> = {
  neutral: 'bg-hover text-fg-2 border-line',
  accent: 'bg-accent-soft text-accent border-transparent',
  up: 'bg-up-soft text-up border-transparent',
  down: 'bg-down-soft text-down border-transparent',
  forecast: 'bg-forecast-soft text-forecast border-transparent',
  warning: 'bg-warning-soft text-warning border-transparent',
  danger: 'bg-danger-soft text-danger border-transparent',
  info: 'bg-info-soft text-info border-transparent',
  demo: 'bg-demo-soft text-demo border-demo/40',
};

export function Badge({ tone = 'neutral', children, className, title }: { tone?: BadgeTone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex h-5 shrink-0 items-center gap-1 rounded-sm border px-1.5 text-xs font-medium whitespace-nowrap',
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Marks simulated content. Used on every panel that shows fixture data so a
 * value can never be mistaken for live market data or real model output.
 */
export function DemoBadge({ label = 'Simulated', detail }: { label?: string; detail?: string }) {
  return (
    <Badge tone="demo" title={detail ?? 'Demo data — generated locally, not real market data or model output.'}>
      <FlaskConical aria-hidden className="size-3" />
      <span>{label}</span>
    </Badge>
  );
}
