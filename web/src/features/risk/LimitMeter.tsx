import type { LimitCheck } from '@/domain/risk';
import { cn } from '@/lib/cn';
import { formatMoney } from '@/lib/format';
import { STATUS_META } from './limitStatus';

/**
 * Utilisation of one limit: what is already used (solid), what this trade adds
 * (hatched), and the limit (end of the track). Status is always stated in
 * words with an icon — never by colour alone.
 */
export function LimitMeter({ check, currency, showTrade = true }: { check: LimitCheck; currency: string; showTrade?: boolean }) {
  const meta = STATUS_META[check.status];
  const Icon = meta.icon;
  const scale = Math.max(check.limit, check.after, 1e-9);
  const usedPct = Math.min(100, (check.used / scale) * 100);
  const addPct = Math.min(100 - usedPct, ((check.after - check.used) / scale) * 100);
  const limitPct = (check.limit / scale) * 100;
  const fmt = (v: number) => (check.unit === 'money' ? formatMoney(v, currency) : String(v));

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-fg">{check.label}</p>
        <p className={cn('inline-flex items-center gap-1 text-xs font-medium', meta.text)}>
          <Icon aria-hidden className="size-3.5" />
          {meta.label}
        </p>
      </div>
      <div
        role="meter"
        aria-label={`${check.label}: ${fmt(showTrade ? check.after : check.used)} of ${fmt(check.limit)}`}
        aria-valuemin={0}
        aria-valuemax={check.limit}
        aria-valuenow={showTrade ? check.after : check.used}
        className="relative h-2 overflow-hidden rounded-full bg-hover"
      >
        <span className={cn('absolute inset-y-0 left-0 rounded-l-full', check.status === 'ok' ? 'bg-fg-3/70' : meta.bar)} style={{ width: `${usedPct}%` }} />
        {showTrade && addPct > 0 && (
          <span
            className={cn('absolute inset-y-0', check.status === 'ok' ? 'bg-accent' : meta.bar)}
            style={{
              left: `${usedPct}%`,
              width: `${addPct}%`,
              backgroundImage: 'repeating-linear-gradient(135deg, transparent 0 3px, rgb(0 0 0 / 0.22) 3px 5px)',
            }}
          />
        )}
        {limitPct < 100 && <span aria-hidden className="absolute inset-y-0 w-0.5 bg-fg" style={{ left: `${limitPct}%` }} />}
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs text-fg-3">
        <span className="num">
          {fmt(check.used)}
          {showTrade && check.after !== check.used && (
            <>
              {' '}
              → <span className="text-fg">{fmt(check.after)}</span>
            </>
          )}{' '}
          of {fmt(check.limit)}
        </span>
        <span className="num">{check.status === 'breach' ? `over by ${fmt(check.after - check.limit)}` : `${fmt(check.remaining)} left`}</span>
      </div>
      <p className="text-xs text-fg-3">{check.rule}</p>
    </div>
  );
}
