import { Loader2, type LucideIcon } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

import { buttonClasses, type ButtonShape as Shape, type ButtonSize as Size, type ButtonVariant as Variant } from './buttonClasses';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  /** Icon after the label (e.g. an arrow on a call to action). */
  trailingIcon?: LucideIcon;
  /** `pill` for narrative calls to action (Overview, auth, empty states); `rect` in dense tools. */
  shape?: Shape;
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean;
  children?: ReactNode;
}

export function Button({ variant = 'secondary', size = 'md', shape = 'rect', icon: Icon, trailingIcon: Trailing, loading = false, className, children, disabled, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, size, shape, className })}
      {...rest}
    >
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : Icon ? <Icon aria-hidden className="size-4" /> : null}
      {children}
      {Trailing && !loading && <Trailing aria-hidden className="size-4" />}
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
