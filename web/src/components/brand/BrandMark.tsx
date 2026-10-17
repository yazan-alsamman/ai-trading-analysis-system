import { cn } from '@/lib/cn';

/**
 * Brand mark: three rising candles (observed market, aurum gold) continued by
 * a dashed violet segment ending in a node (the AI forecast). It encodes the
 * product's core rule — observed and predicted are always distinguishable.
 */
export function BrandGlyph({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn('shrink-0', className)}>
      <rect x="0.5" y="0.5" width="31" height="31" rx="9" className="fill-raised stroke-line-strong" />
      <g className="stroke-accent" strokeWidth="1.5" strokeLinecap="round">
        <line x1="8" y1="15" x2="8" y2="25" />
        <line x1="14" y1="11" x2="14" y2="22" />
        <line x1="20" y1="7.5" x2="20" y2="18" />
      </g>
      <g className="fill-accent">
        <rect x="6" y="17.5" width="4" height="5.5" rx="1" />
        <rect x="12" y="13.5" width="4" height="6" rx="1" />
        <rect x="18" y="10" width="4" height="5.5" rx="1" />
      </g>
      <path d="M22.6 9.6 L25.9 6.6" className="stroke-forecast" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="1.4 1.8" />
      <circle cx="26.6" cy="6" r="1.9" className="fill-forecast" />
    </svg>
  );
}

export function BrandMark({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <BrandGlyph className="size-8" />
      {!collapsed && (
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-semibold tracking-tight text-fg">
            AI Trading <span className="font-normal text-fg-2">Assistance</span>
          </p>
          <p className="truncate font-mono text-xs tracking-[0.08em] text-fg-3 uppercase">Gold &amp; FX research</p>
        </div>
      )}
    </div>
  );
}
