import type { LucideIcon } from 'lucide-react';
import { useRef, type KeyboardEvent } from 'react';
import { cn } from '@/lib/cn';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: LucideIcon;
  /** Hide the text label (icon still needs `label` for the accessible name). */
  iconOnly?: boolean;
  title?: string;
}

interface Props<T extends string> {
  label: string;
  value: T;
  options: readonly SegmentOption<T>[];
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
  className?: string;
}

/** Radio group styled as segments. Arrow keys move the selection (WAI-ARIA radio pattern). */
export function SegmentedControl<T extends string>({ label, value, options, onChange, size = 'sm', className }: Props<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const delta = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const next = (index + delta + options.length) % options.length;
    const option = options[next];
    if (option) {
      onChange(option.value);
      refs.current[next]?.focus();
    }
  };

  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex rounded-md border border-line bg-inset p-0.5', className)}>
      {options.map((option, index) => {
        const selected = option.value === value;
        const Icon = option.icon;
        return (
          <button
            key={option.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={option.iconOnly ? option.label : undefined}
            title={option.title ?? (option.iconOnly ? option.label : undefined)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(e) => onKeyDown(e, index)}
            className={cn(
              'inline-flex items-center justify-center gap-1.5 rounded-sm font-medium transition-colors duration-150',
              size === 'sm' ? 'h-7 min-w-8 px-2 text-sm' : 'h-8 min-w-9 px-3 text-sm',
              selected ? 'bg-selected text-fg shadow-[inset_0_0_0_1px_var(--line-strong)]' : 'text-fg-2 hover:text-fg',
            )}
          >
            {Icon && <Icon aria-hidden className="size-4" />}
            {!option.iconOnly && <span>{option.label}</span>}
          </button>
        );
      })}
    </div>
  );
}
