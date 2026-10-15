import { useId, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface PanelProps {
  title: ReactNode;
  /** Small text after the title (metadata, counts). */
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Use for panels whose body handles its own padding (tables, charts). */
  flush?: boolean;
}

/** Bordered section with a labelled header — the basic layout unit. */
export function Panel({ title, meta, actions, children, className, bodyClassName, flush = false }: PanelProps) {
  const id = useId();
  return (
    <section aria-labelledby={id} className={cn('flex min-w-0 flex-col rounded-lg border border-line bg-surface', className)}>
      <header className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-2">
        <h2 id={id} className="text-sm font-semibold text-fg">
          {title}
        </h2>
        {meta && <div className="flex min-w-0 items-center gap-2 text-xs text-fg-3">{meta}</div>}
        {actions && <div className="ml-auto flex items-center gap-1.5">{actions}</div>}
      </header>
      <div className={cn('min-h-0 flex-1', !flush && 'p-4', bodyClassName)}>{children}</div>
    </section>
  );
}

/**
 * Standard page frame. `wide` for data pages (tables, statistics), `reading`
 * for text-first pages and forms — one consistent rhythm across routes.
 */
export function Page({ width = 'wide', children, className }: { width?: 'wide' | 'reading'; children: ReactNode; className?: string }) {
  return (
    <div className={cn('mx-auto flex w-full flex-col gap-5 px-4 py-5 sm:px-6', width === 'wide' ? 'max-w-[1600px]' : 'max-w-5xl', className)}>
      {children}
    </div>
  );
}

export function PageHeader({ title, description, actions, meta }: { title: string; description?: ReactNode; actions?: ReactNode; meta?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg leading-tight font-semibold tracking-tight text-fg">{title}</h1>
          {meta}
        </div>
        {description && <p className="mt-1 max-w-3xl text-sm text-fg-3">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A label/value pair for compact metric grids. */
export function Stat({ label, value, hint, className }: { label: ReactNode; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn('min-w-0', className)}>
      <dt className="text-xs text-fg-3">{label}</dt>
      <dd className="mt-0.5 text-base text-fg">{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-fg-3">{hint}</dd>}
    </div>
  );
}
