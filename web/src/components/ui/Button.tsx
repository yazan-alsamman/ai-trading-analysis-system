import { Loader2, type LucideIcon } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover border border-transparent',
  secondary: 'bg-surface text-fg border border-line-strong hover:bg-hover',
  ghost: 'bg-transparent text-fg-2 border border-transparent hover:bg-hover hover:text-fg',
  danger: 'bg-transparent text-danger border border-danger/50 hover:bg-danger-soft',
};

const SIZE: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-sm gap-1.5',
  md: 'h-9 px-3.5 text-base gap-2',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean;
  children?: ReactNode;
}

export function Button({ variant = 'secondary', size = 'md', icon: Icon, loading = false, className, children, disabled, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-md font-medium whitespace-nowrap transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : Icon ? <Icon aria-hidden className="size-4" /> : null}
      {children}
    </button>
  );
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  icon: LucideIcon;
  /** Required: becomes the accessible name and the visible tooltip. */
  label: string;
  size?: Size;
  active?: boolean;
  tooltipSide?: 'top' | 'bottom' | 'left' | 'right';
}

const TOOLTIP_SIDE = {
  top: 'bottom-full left-1/2 mb-1.5 -translate-x-1/2',
  bottom: 'top-full left-1/2 mt-1.5 -translate-x-1/2',
  left: 'right-full top-1/2 mr-1.5 -translate-y-1/2',
  right: 'left-full top-1/2 ml-1.5 -translate-y-1/2',
} as const;

export function IconButton({ icon: Icon, label, size = 'md', active = false, tooltipSide = 'bottom', className, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      className={cn(
        'group relative inline-flex shrink-0 items-center justify-center rounded-md border border-transparent text-fg-2 transition-colors duration-150',
        'hover:bg-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-50',
        active && 'bg-selected text-fg',
        size === 'sm' ? 'size-7' : 'size-9',
        className,
      )}
      {...rest}
    >
      <Icon aria-hidden className="size-4" />
      <span
        aria-hidden
        className={cn(
          'pointer-events-none absolute z-50 hidden rounded-sm border border-line-strong bg-raised px-2 py-1 text-xs whitespace-nowrap text-fg shadow-float',
          'group-hover:block group-focus-visible:block',
          TOOLTIP_SIDE[tooltipSide],
        )}
      >
        {label}
      </span>
    </button>
  );
}
