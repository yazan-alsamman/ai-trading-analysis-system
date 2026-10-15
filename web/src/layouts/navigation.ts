import { BellRing, CandlestickChart, Gauge, MessagesSquare, Radar, Settings, type LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
  /** Two-key shortcut, e.g. "g w". */
  shortcut: string;
}

export interface NavGroup {
  label: string;
  items: readonly NavItem[];
}

/** Primary navigation grouped by trader task. */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: 'Trade',
    items: [
      { to: '/workspace', label: 'Workspace', icon: CandlestickChart, description: 'Chart, watchlist and AI opportunity', shortcut: 'g w' },
      { to: '/signals', label: 'Signals', icon: Radar, description: 'AI opportunities across instruments', shortcut: 'g s' },
    ],
  },
  {
    label: 'Monitor',
    items: [
      { to: '/alerts', label: 'Alerts', icon: BellRing, description: 'Price alerts and opportunity notifications', shortcut: 'g a' },
      { to: '/insights', label: 'Insights', icon: Gauge, description: 'Prediction statistics and history', shortcut: 'g i' },
    ],
  },
  {
    label: 'Connect',
    items: [{ to: '/community', label: 'Community', icon: MessagesSquare, description: 'News, posts and experts', shortcut: 'g c' }],
  },
];

export const SETTINGS_NAV: NavItem = {
  to: '/settings',
  label: 'Settings',
  icon: Settings,
  description: 'Theme, time zone, channels, workspaces',
  shortcut: 'g ,',
};

export const ALL_NAV: readonly NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), SETTINGS_NAV];

const SUB_PAGES: Record<string, string> = {
  '/community/news': 'News',
  '/community/posts': 'Posts',
  '/community/experts': 'Experts',
};

/** Breadcrumb for the top bar: group › page (› sub-page). */
export function breadcrumbFor(pathname: string): string[] {
  const item = ALL_NAV.find((n) => pathname === n.to || pathname.startsWith(`${n.to}/`));
  if (!item) return ['Not found'];
  const group = NAV_GROUPS.find((g) => g.items.includes(item))?.label;
  const crumbs = [...(group ? [group] : []), item.label];
  const sub = SUB_PAGES[pathname];
  return sub ? [...crumbs, sub] : crumbs;
}

/** Shortcut-key → path, for the global hotkey handler. */
export const NAV_SHORTCUTS: Record<string, string> = Object.fromEntries(ALL_NAV.map((n) => [n.shortcut, n.to]));
