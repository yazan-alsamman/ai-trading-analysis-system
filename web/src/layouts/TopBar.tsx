import { ChevronRight, Keyboard, LogIn, LogOut, Menu, Moon, Search, Sun, UserRound } from 'lucide-react';
import { useId } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { useAuth, usePreferences, useServices, useToast } from '@/app/contexts';
import { BrandGlyph } from '@/components/brand/BrandMark';
import { Badge } from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/Button';
import { Popover } from '@/components/ui/Popover';
import { sessionSummary } from '@/domain/sessions';
import { ROLE_LABELS } from '@/domain/user';
import { useNow, useOnlineStatus } from '@/hooks/useEnvironment';
import { cn } from '@/lib/cn';
import { formatClock } from '@/lib/format';
import { breadcrumbFor } from './navigation';
import { NotificationCenter } from './NotificationCenter';

function Breadcrumb() {
  const { pathname } = useLocation();
  const crumbs = breadcrumbFor(pathname);
  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 md:block">
      <ol className="flex items-center gap-1 text-sm">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={c} className="flex min-w-0 items-center gap-1">
              {i > 0 && <ChevronRight aria-hidden className="size-3.5 shrink-0 text-fg-3" />}
              <span aria-current={last ? 'page' : undefined} className={cn('truncate', last ? 'font-medium text-fg' : 'text-fg-3')}>
                {c}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Global market status: session, UTC clock and data mode. Visible on every page. */
function MarketStatus() {
  const now = useNow(1000);
  const online = useOnlineStatus();
  const { source } = useServices();
  const summary = sessionSummary(now);
  const closed = summary.startsWith('Market closed');
  return (
    <div className="hidden items-center gap-3 rounded-md border border-line bg-inset px-2.5 py-1 text-xs xl:flex" aria-label="Market status">
      <span className="flex items-center gap-1.5">
        <span aria-hidden className={cn('size-1.5 rounded-full', !online ? 'bg-danger' : closed ? 'bg-fg-3' : 'bg-accent')} />
        <span className="text-fg-2">{!online ? 'Offline' : summary}</span>
      </span>
      <span aria-hidden className="h-3 w-px bg-line-strong" />
      <span className="num text-fg" title="Coordinated Universal Time — the reference for all market data">
        {formatClock(now, 'UTC')} <span className="text-fg-3">UTC</span>
      </span>
      {source === 'demo' && (
        <>
          <span aria-hidden className="h-3 w-px bg-line-strong" />
          <span className="font-medium text-demo" title="All market data, AI output and statistics are simulated in the browser.">
            Demo data
          </span>
        </>
      )}
    </div>
  );
}

function WorkspaceSwitcher() {
  const { prefs, setActiveWorkspace } = usePreferences();
  const id = useId();
  return (
    <div className="flex min-w-0 items-center">
      <label htmlFor={id} className="sr-only">
        Active workspace
      </label>
      <select
        id={id}
        value={prefs.activeWorkspaceId}
        onChange={(e) => setActiveWorkspace(e.target.value)}
        className="h-8 max-w-36 min-w-0 cursor-pointer truncate rounded-md border border-line bg-inset px-2 text-sm text-fg hover:border-line-strong sm:max-w-44"
      >
        {prefs.workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function UserMenu({ onShowShortcuts }: { onShowShortcuts: () => void }) {
  const { session, logout } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();

  if (!session) {
    return (
      <Link to="/login" className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium text-fg-2 hover:bg-hover hover:text-fg">
        <LogIn aria-hidden className="size-4" />
        <span className="hidden sm:inline">Sign in</span>
      </Link>
    );
  }

  const initials = session.user.name
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <Popover
      label="Account"
      align="end"
      trigger={(t) => (
        <button
          type="button"
          {...t}
          aria-label={`Account menu for ${session.user.name}`}
          className="inline-flex size-8 items-center justify-center rounded-full bg-selected text-xs font-semibold text-fg ring-1 ring-line-strong hover:ring-accent"
        >
          {initials || <UserRound aria-hidden className="size-4" />}
        </button>
      )}
    >
      {(close) => (
        <div className="w-64">
          <div className="border-b border-line px-2.5 pt-1.5 pb-2.5">
            <p className="truncate text-sm font-medium text-fg">{session.user.name}</p>
            <p className="truncate text-xs text-fg-3">{session.user.email}</p>
            <div className="mt-2 flex gap-1.5">
              <Badge>{ROLE_LABELS[session.user.role]}</Badge>
              {session.isDemo && <Badge tone="demo">Demo session</Badge>}
            </div>
          </div>
          <div className="mt-1 flex flex-col">
            <button
              type="button"
              onClick={() => {
                close();
                onShowShortcuts();
              }}
              className="flex h-9 items-center gap-2 rounded-md px-2.5 text-sm text-fg-2 hover:bg-hover hover:text-fg"
            >
              <Keyboard aria-hidden className="size-4" /> Keyboard shortcuts
            </button>
            <button
              type="button"
              onClick={async () => {
                close();
                await logout();
                notify('Signed out.', 'info');
                navigate('/login');
              }}
              className="flex h-9 items-center gap-2 rounded-md px-2.5 text-sm text-fg-2 hover:bg-hover hover:text-fg"
            >
              <LogOut aria-hidden className="size-4" /> Sign out
            </button>
          </div>
        </div>
      )}
    </Popover>
  );
}

export function TopBar({ onOpenMenu, onOpenSearch, onShowShortcuts }: { onOpenMenu: () => void; onOpenSearch: () => void; onShowShortcuts: () => void }) {
  const { resolvedTheme, setTheme } = usePreferences();
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

  return (
    <header className="flex h-[var(--topbar-h)] shrink-0 items-center gap-2 border-b border-line bg-surface px-3 sm:gap-3 sm:px-4">
      {/* Wrappers own responsive display so it never fights a component's own display class. */}
      <div className="lg:hidden">
        <IconButton icon={Menu} label="Open navigation" onClick={onOpenMenu} tooltipSide="right" />
      </div>
      <div className="hidden sm:block lg:hidden">
        <BrandGlyph className="size-7" />
      </div>
      <Breadcrumb />
      <span aria-hidden className="hidden h-5 w-px bg-line md:block" />
      <WorkspaceSwitcher />

      <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
        <div className="hidden md:block">
          <button
            type="button"
            onClick={onOpenSearch}
            aria-keyshortcuts="Control+K Meta+K"
            className="inline-flex h-8 w-52 items-center gap-2 rounded-md border border-line bg-inset px-2.5 text-sm text-fg-3 hover:border-line-strong hover:text-fg-2"
          >
            <Search aria-hidden className="size-4" />
            <span className="flex-1 text-left">Search…</span>
            <kbd className="num rounded-sm border border-line px-1 text-xs">{isMac ? '⌘K' : 'Ctrl K'}</kbd>
          </button>
        </div>
        <div className="md:hidden">
          <IconButton icon={Search} label="Search instruments and pages" onClick={onOpenSearch} />
        </div>
        <MarketStatus />
        <NotificationCenter />
        <IconButton
          icon={resolvedTheme === 'dark' ? Sun : Moon}
          label={resolvedTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          tooltipSide="left"
        />
        <UserMenu onShowShortcuts={onShowShortcuts} />
      </div>
    </header>
  );
}
