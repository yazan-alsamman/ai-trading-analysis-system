import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { NavLink } from 'react-router';
import { BrandMark } from '@/components/brand/BrandMark';
import { IconButton } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import { MarketSessions } from './MarketSessions';
import { NAV_GROUPS, SETTINGS_NAV, type NavItem } from './navigation';

function Shortcut({ keys }: { keys: string }) {
  return (
    <span aria-hidden className="ml-auto hidden gap-0.5 group-hover:flex group-focus-visible:flex">
      {keys.split(' ').map((k) => (
        <kbd key={k} className="num rounded-sm border border-line px-1 text-xs leading-4 text-fg-3 uppercase">
          {k}
        </kbd>
      ))}
    </span>
  );
}

function NavEntry({ item, collapsed, onNavigate }: { item: NavItem; collapsed: boolean; onNavigate: (() => void) | undefined }) {
  const Icon = item.icon;
  return (
    <li>
      <NavLink
        to={item.to}
        onClick={onNavigate}
        title={collapsed ? `${item.label} (${item.shortcut.toUpperCase()})` : undefined}
        className={({ isActive }) =>
          cn(
            'group relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors duration-150',
            isActive ? 'bg-selected font-medium text-fg' : 'text-fg-2 hover:bg-hover hover:text-fg',
            collapsed && 'justify-center px-0',
          )
        }
      >
        {({ isActive }) => (
          <>
            {isActive && <span aria-hidden className="absolute top-1.5 bottom-1.5 -left-2 w-0.5 rounded-full bg-accent" />}
            <Icon aria-hidden className={cn('size-4 shrink-0', isActive && 'text-accent')} />
            <span className={cn(collapsed && 'sr-only')}>{item.label}</span>
            {!collapsed && <Shortcut keys={item.shortcut} />}
          </>
        )}
      </NavLink>
    </li>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed?: () => void;
  onNavigate?: () => void;
  className?: string;
}

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate, className }: SidebarProps) {
  return (
    <div className={cn('flex h-full flex-col bg-surface', className)}>
      <div className={cn('flex h-[var(--topbar-h)] shrink-0 items-center border-b border-line', collapsed ? 'justify-center' : 'px-3.5')}>
        <BrandMark collapsed={collapsed} />
      </div>
      <nav aria-label="Primary" className="flex min-h-0 flex-1 flex-col overflow-y-auto px-2 py-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-3">
            {collapsed ? (
              <span aria-hidden className="mx-auto mb-1.5 block h-px w-5 bg-line" />
            ) : (
              <h2 className="mb-1 px-2.5 text-xs font-medium text-fg-3">{group.label}</h2>
            )}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => (
                <NavEntry key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
              ))}
            </ul>
          </div>
        ))}
        <div className="mt-auto flex flex-col gap-3 border-t border-line pt-3">
          <MarketSessions collapsed={collapsed} />
          <ul className="flex flex-col gap-0.5">
            <NavEntry item={SETTINGS_NAV} collapsed={collapsed} onNavigate={onNavigate} />
          </ul>
          {onToggleCollapsed && (
            <div className={cn('flex', collapsed ? 'justify-center' : 'justify-end')}>
              <IconButton
                icon={collapsed ? PanelLeftOpen : PanelLeftClose}
                label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                size="sm"
                onClick={onToggleCollapsed}
                tooltipSide="right"
              />
            </div>
          )}
        </div>
      </nav>
    </div>
  );
}
