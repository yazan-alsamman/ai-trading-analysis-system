import { cn } from '@/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';
export type ButtonShape = 'rect' | 'pill';

const VARIANT: Record<ButtonVariant, string> = {
  /* Inverted neutral: white on ink / ink on paper. One primary action per view. */
  primary: 'bg-primary text-primary-fg hover:bg-primary-hover border border-transparent shadow-[0_1px_0_rgb(255_255_255/0.06)_inset]',
  secondary: 'bg-surface text-fg border border-line-strong hover:bg-hover',
  ghost: 'bg-transparent text-fg-2 border border-transparent hover:bg-hover hover:text-fg',
  danger: 'bg-transparent text-danger border border-danger/50 hover:bg-danger-soft',
};

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-sm gap-1.5',
  md: 'h-9 px-3.5 text-base gap-2',
  lg: 'h-11 px-5 text-md gap-2',
};

/** Shared class list so links can look exactly like buttons (see `buttonClasses`). */
export function buttonClasses({ variant = 'secondary', size = 'md', shape = 'rect', className }: { variant?: ButtonVariant; size?: ButtonSize; shape?: ButtonShape; className?: string | undefined } = {}): string {
  return cn(
    'inline-flex shrink-0 items-center justify-center font-medium whitespace-nowrap transition-[background-color,color,border-color,transform] duration-150 active:translate-y-px',
    'disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
    shape === 'pill' ? 'rounded-full' : 'rounded-md',
    VARIANT[variant],
    SIZE[size],
    className,
  );
}

