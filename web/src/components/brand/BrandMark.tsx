import { cn } from '@/lib/cn';

/**
 * Brand mark: three rising candles (observed market, accent blue) continued by
 * a dashed violet segment ending in a node (the AI forecast). It encodes the
 * product's core rule — observed and predicted are always distinguishable.
 */
export function BrandGlyph({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn('shrink-0', className)}>
      <rect width="32" height="32" rx="8" className="fill-selected" />
      <g className="stroke-accent" strokeWidth="1.6" strokeLinecap="round">
        <line x1="8" y1="14" x2="8" y2="25" />
        <line x1="14" y1="10" x2="14" y2="22" />
        <line x1="20" y1="7" x2="20" y2="18" />
      </g>
      <g className="fill-accent">
        <rect x="6" y="17" width="4" height="6" rx="1" />
        <rect x="12" y="13" width="4" height="6.5" rx="1" />
        <rect x="18" y="9.5" width="4" height="6" rx="1" />
      </g>
      <path d="M22.5 9.5 L26 6.5" className="stroke-forecast" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="1.6 1.8" />
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
          <p className="truncate text-xs text-fg-3">Forex intelligence</p>
        </div>
      )}
    </div>
  );
}
