import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';
import type { SortState } from '@/lib/sort';

/**
 * Horizontally scrollable table region. Scrolling is contained here, never
 * on the page, and the region is focusable + labelled for keyboard users.
 */
export function TableRegion({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    // tabIndex: a scrollable region must be keyboard reachable (WCAG 2.1.1).
    // `relative` makes this the containing block for visually-hidden (absolute)
    // text in cells, so it is clipped here instead of widening the page.
    <div role="region" aria-label={label} tabIndex={0} className={cn('relative w-full overflow-x-auto', className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ className, numeric, children, ...rest }: ThHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={cn(
        'sticky top-0 z-[1] h-9 border-b border-line bg-surface px-3 text-xs font-medium whitespace-nowrap text-fg-3',
        numeric ? 'text-right' : 'text-left',
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export function SortableTh<K extends string>({
  sortKey,
  sort,
  onSort,
  children,
  numeric,
  className,
}: {
  sortKey: K;
  sort: SortState<K>;
  onSort: (key: K) => void;
  children: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.direction === 'asc' ? ArrowUp : ArrowDown;
  return (
    <Th numeric={numeric ?? false} aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'} className={cn('p-0', className)}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          'inline-flex h-9 w-full items-center gap-1 px-3 hover:text-fg',
          numeric && 'justify-end',
          active && 'text-fg',
        )}
      >
        {children}
        <Icon aria-hidden className={cn('size-3.5', !active && 'opacity-50')} />
      </button>
    </Th>
  );
}

export function Td({ className, numeric, ...rest }: TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return <td className={cn('h-row border-b border-line px-3 py-1.5 whitespace-nowrap text-fg', numeric && 'num text-right', className)} {...rest} />;
}
