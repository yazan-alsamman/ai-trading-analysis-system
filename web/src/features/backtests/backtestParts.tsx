import { Info } from 'lucide-react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import type { BacktestStatus } from '@/domain/backtests';
import { cn } from '@/lib/cn';
import { STATUS_LABEL } from './backtestFormat';

const STATUS_TONE: Record<BacktestStatus, BadgeTone> = {
  queued: 'neutral',
  running: 'info',
  completed: 'up',
  failed: 'danger',
  cancelled: 'warning',
};

export function StatusBadge({ status }: { status: BacktestStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}

/** Server-reported progress: 5 started, 30 candles loaded, 80 computed, 100 saved. */
export function ProgressBar({ value, label, className }: { value: number; label: string; className?: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className={cn('h-1.5 w-full min-w-16 overflow-hidden rounded-full bg-hover', className)}
    >
      <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function BacktestDisclaimer({ className }: { className?: string }) {
  return (
    <p className={cn('flex items-start gap-2 text-xs text-fg-3', className)}>
      <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span>
        Backtests replay a strategy over historical candles stored by the backend, with fees and slippage. Past performance is not a forecast and not financial
        advice. The platform never places, modifies or closes trades.
      </span>
    </p>
  );
}
