import { ArrowDownRight, ArrowUpRight, Minus, MoveRight } from 'lucide-react';
import type { FeedStatus } from '@/domain/market';
import type { Direction } from '@/domain/opportunity';
import { cn } from '@/lib/cn';
import { trendOf, type Trend } from '@/lib/format';
import { Badge } from './Badge';

const TREND_CLASS: Record<Trend, string> = { up: 'text-up', down: 'text-down', flat: 'text-fg-2' };

export function TrendIcon({ trend, className }: { trend: Trend; className?: string }) {
  const Icon = trend === 'up' ? ArrowUpRight : trend === 'down' ? ArrowDownRight : Minus;
  return <Icon aria-hidden className={cn('size-3.5 shrink-0', className)} />;
}

/**
 * A signed change: colour + arrow + sign + screen-reader wording.
 * Colour is never the only cue (WCAG 1.4.1).
 */
export function ChangeText({ value, text, className, showIcon = true }: { value: number | null | undefined; text: string; className?: string; showIcon?: boolean }) {
  const trend = trendOf(value);
  const srWord = trend === 'up' ? 'up' : trend === 'down' ? 'down' : 'unchanged';
  return (
    <span className={cn('num inline-flex items-center gap-0.5 whitespace-nowrap', TREND_CLASS[trend], className)}>
      {showIcon && <TrendIcon trend={trend} />}
      <span aria-hidden>{text}</span>
      <span className="sr-only">
        {srWord} {text.replace(/^[+−]/, '')}
      </span>
    </span>
  );
}

/** Long / Short / Neutral — market direction, so up/down colours apply. */
export function DirectionBadge({ direction, className }: { direction: Direction; className?: string }) {
  if (direction === 'long')
    return (
      <Badge tone="up" className={className}>
        <ArrowUpRight aria-hidden className="size-3" /> Long
      </Badge>
    );
  if (direction === 'short')
    return (
      <Badge tone="down" className={className}>
        <ArrowDownRight aria-hidden className="size-3" /> Short
      </Badge>
    );
  return (
    <Badge tone="neutral" className={className}>
      <MoveRight aria-hidden className="size-3" /> Neutral
    </Badge>
  );
}

const FEED: Record<FeedStatus, { label: string; dot: string; text: string; description: string }> = {
  live: { label: 'Live', dot: 'bg-accent', text: 'text-fg-2', description: 'Receiving real-time updates from the backend.' },
  demo: { label: 'Simulated feed', dot: 'bg-demo', text: 'text-demo', description: 'Prices are generated locally for demonstration. Not real market data.' },
  connecting: { label: 'Connecting', dot: 'bg-fg-3', text: 'text-fg-2', description: 'Establishing the price feed.' },
  delayed: { label: 'Delayed', dot: 'bg-warning', text: 'text-warning', description: 'Updates are arriving late.' },
  stale: { label: 'Stale', dot: 'bg-warning', text: 'text-warning', description: 'No price update recently. Values may be out of date.' },
  closed: { label: 'Market closed', dot: 'bg-fg-3', text: 'text-fg-2', description: 'The FX market is closed (weekend). Prices resume Sunday 22:00 UTC.' },
  offline: { label: 'Offline', dot: 'bg-danger', text: 'text-danger', description: 'No network connection. Showing the last received data.' },
  error: { label: 'Feed error', dot: 'bg-danger', text: 'text-danger', description: 'The price feed failed. Retrying automatically.' },
};

/** Connection / freshness indicator. Text label always present. */
export function FeedStatusPill({ status, className }: { status: FeedStatus; className?: string }) {
  const f = FEED[status];
  return (
    <span title={f.description} className={cn('inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap', f.text, className)}>
      <span aria-hidden className={cn('size-1.5 rounded-full', f.dot)} />
      <span>{f.label}</span>
    </span>
  );
}
