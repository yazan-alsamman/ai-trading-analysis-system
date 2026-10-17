import { NavLink } from 'react-router';
import { cn } from '@/lib/cn';

/** Route-backed tabs: each tab is a real link, so URLs are shareable and Back works. */
export function RouteTabs({ label, tabs }: { label: string; tabs: readonly { to: string; label: string; end?: boolean }[] }) {
  return (
    <nav aria-label={label} className="-mb-px flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end ?? true}
          className={({ isActive }) =>
            cn(
              'inline-flex h-9 items-center border-b-2 px-3 text-sm font-medium whitespace-nowrap transition-colors',
              isActive ? 'border-accent text-fg' : 'border-transparent text-fg-2 hover:text-fg',
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
