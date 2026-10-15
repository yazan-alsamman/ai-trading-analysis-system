import { FlaskConical, WifiOff, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router';
import { z } from 'zod';
import { usePreferences, useServices } from '@/app/contexts';
import { IconButton } from '@/components/ui/Button';
import { AlertMonitor } from '@/features/alerts/AlertMonitor';
import { useOnlineStatus } from '@/hooks/useEnvironment';
import { useHotkeys } from '@/hooks/useHotkeys';
import { readStored, writeStored } from '@/lib/storage';
import { CommandPalette } from './CommandPalette';
import { NAV_SHORTCUTS } from './navigation';
import { ShortcutsDialog } from './ShortcutsDialog';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

const COLLAPSE_KEY = 'ata.sidebarCollapsed.v1';
const BANNER_KEY = 'ata.demoBannerDismissed';

/**
 * Explains demo mode on first view. It can be dismissed for the browser
 * session; the "Demo data" indicator in the top bar and every "Simulated"
 * badge remain, so simulated data is never unlabelled.
 */
function DemoBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="relative flex min-h-7 shrink-0 items-center justify-center gap-2 border-b border-demo/25 bg-demo-soft px-10 py-1 text-center text-xs text-fg-2">
      <FlaskConical aria-hidden className="size-3.5 shrink-0 text-demo" />
      <p>
        <strong className="font-semibold text-demo">Demo mode.</strong> Prices, AI opportunities and statistics are simulated.
        <span className="hidden md:inline"> Analysis only — not financial advice; this platform never executes trades.</span>{' '}
        <Link to="/settings#data-source" className="underline underline-offset-2 hover:text-fg">
          Details
        </Link>
      </p>
      <div className="absolute right-2">
        <IconButton icon={X} label="Hide demo notice for this session" size="sm" onClick={onDismiss} tooltipSide="left" />
      </div>
    </div>
  );
}

function OfflineBanner() {
  return (
    <div role="status" className="flex shrink-0 items-center justify-center gap-2 border-b border-danger/40 bg-danger-soft px-4 py-1.5 text-xs text-fg">
      <WifiOff aria-hidden className="size-3.5 text-danger" />
      You are offline. Showing the last received data; values may be out of date.
    </div>
  );
}

/** Mobile/tablet navigation drawer on a native <dialog> (focus trap + Esc). */
function NavDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-label="Navigation"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-0 h-dvh max-h-dvh w-[min(280px,85vw)] max-w-none border-r border-line bg-surface p-0 backdrop:bg-overlay"
    >
      <div className="relative h-full">
        <div className="absolute top-2.5 right-2 z-10">
          <IconButton icon={X} label="Close navigation" size="sm" onClick={onClose} tooltipSide="left" />
        </div>
        <Sidebar collapsed={false} onNavigate={onClose} />
      </div>
    </dialog>
  );
}

function readSessionFlag(key: string): boolean {
  try {
    return window.sessionStorage.getItem(key) === '1';
  } catch {
    return false;
  }
}

export function AppShell() {
  const { source } = useServices();
  const { resolvedTheme, setTheme } = usePreferences();
  const online = useOnlineStatus();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(() => readStored(COLLAPSE_KEY, z.boolean(), false));
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [bannerHidden, setBannerHidden] = useState(() => readSessionFlag(BANNER_KEY));
  const location = useLocation();

  useEffect(() => writeStored(COLLAPSE_KEY, collapsed), [collapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const hotkeys = useMemo(
    () => ({
      '?': () => setShortcutsOpen(true),
      t: () => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark'),
      ...Object.fromEntries(Object.entries(NAV_SHORTCUTS).map(([keys, to]) => [keys, () => navigate(to)])),
    }),
    [navigate, resolvedTheme, setTheme],
  );
  useHotkeys(hotkeys);

  // On client-side navigation, move focus to <main> so screen-reader users hear the
  // new page. Skipped on first load so the skip link stays the first Tab stop.
  const mainRef = useRef<HTMLElement>(null);
  const firstPath = useRef(location.pathname);
  useEffect(() => {
    if (location.pathname === firstPath.current) return;
    firstPath.current = '';
    mainRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const dismissBanner = () => {
    setBannerHidden(true);
    try {
      window.sessionStorage.setItem(BANNER_KEY, '1');
    } catch {
      /* storage unavailable — hidden for this page view only */
    }
  };

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg"
      >
        Skip to main content
      </a>
      {source === 'demo' && !bannerHidden && <DemoBanner onDismiss={dismissBanner} />}
      {!online && <OfflineBanner />}
      <div className="flex min-h-0 flex-1">
        <aside
          className="hidden shrink-0 border-r border-line lg:block"
          style={{ width: collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)' }}
        >
          <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((c) => !c)} />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar onOpenMenu={() => setDrawerOpen(true)} onOpenSearch={() => setSearchOpen(true)} onShowShortcuts={() => setShortcutsOpen(true)} />
          <main id="main" ref={mainRef} tabIndex={-1} className="relative min-h-0 flex-1 overflow-y-auto outline-none">
            <Outlet />
          </main>
        </div>
      </div>
      <NavDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <CommandPalette open={searchOpen} onClose={closeSearch} />
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <AlertMonitor />
    </div>
  );
}
