import {
  BellRing,
  Bot,
  CalendarDays,
  Crosshair,
  CandlestickChart,
  FlaskConical,
  Workflow,
  Compass,
  Gauge,
  MessagesSquare,
  Radar,
  Scale,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import type { DataSource } from '@/services/config';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
  /** Two-key shortcut, e.g. "g w". */
  shortcut: string;
  /** Needs the backend (hidden in demo mode, where it could only say "not available"). */
  backendOnly?: boolean;
}

export interface NavGroup {
  label: string;
  items: readonly NavItem[];
}

export const OVERVIEW_NAV: NavItem = {
  to: '/overview',
  label: 'Overview',
  icon: Compass,
  description: 'What the platform does, today’s research state and the next step',
  shortcut: 'g o',
};

const WORKSPACE: NavItem = { to: '/workspace', label: 'Workspace', icon: CandlestickChart, description: 'Chart, watchlist and AI research panel', shortcut: 'g w' };
const SIGNALS: NavItem = { to: '/signals', label: 'Signals', icon: Radar, description: 'Model outputs filtered by your profile and risk limits', shortcut: 'g s' };
const ASSISTANT: NavItem = { to: '/assistant', label: 'Assistant', icon: Bot, description: 'Ask about the analysis, its evidence and your risk', shortcut: 'g p' };
const RISK: NavItem = { to: '/risk', label: 'Capital & risk', icon: Scale, description: 'Position size, money at risk and your limits', shortcut: 'g r' };
const ALERTS: NavItem = { to: '/alerts', label: 'Alerts', icon: BellRing, description: 'Price alerts and opportunity notifications', shortcut: 'g a' };
const INSIGHTS: NavItem = { to: '/insights', label: 'Insights', icon: Gauge, description: 'Model accuracy, calibration and history', shortcut: 'g i' };
const COMMUNITY: NavItem = { to: '/community', label: 'Community', icon: MessagesSquare, description: 'Market news, posts and experts', shortcut: 'g c' };
const STRATEGIES: NavItem = {
  to: '/strategies',
  label: 'Strategies',
  icon: Workflow,
  description: 'Rule-based strategies: activate, build your own, preview on a chart',
  shortcut: 'g t',
  backendOnly: true,
};
const AI_SETUPS: NavItem = {
  to: '/ai-setups',
  label: 'AI setups',
  icon: Crosshair,
  description: 'Follow instruments, see setups the AI engine armed, size and record them',
  shortcut: 'g e',
  backendOnly: true,
};
const CALENDAR: NavItem = { to: '/calendar', label: 'Economic calendar', icon: CalendarDays, description: 'Scheduled macro events by currency and impact', shortcut: 'g n', backendOnly: true };
const BACKTESTS: NavItem = { to: '/backtests', label: 'Backtests', icon: FlaskConical, description: 'Replay a strategy on historical candles', shortcut: 'g b', backendOnly: true };

/** Primary navigation, grouped by the research workflow. */
export const NAV_GROUPS: readonly NavGroup[] = [
  { label: 'Research', items: [WORKSPACE, SIGNALS, AI_SETUPS, STRATEGIES, ASSISTANT] },
  { label: 'Risk & monitoring', items: [RISK, ALERTS] },
  { label: 'Review', items: [BACKTESTS, INSIGHTS] },
  { label: 'Market intelligence', items: [CALENDAR, COMMUNITY] },
];

/** The groups shown for a data source (backend-only pages are hidden in demo mode). */
export function navGroupsFor(source: DataSource): NavGroup[] {
  return NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => source === 'api' || !i.backendOnly) })).filter((g) => g.items.length > 0);
}

export const SETTINGS_NAV: NavItem = {
  to: '/settings',
  label: 'Settings',
  icon: Settings,
  description: 'Theme, time zone, channels, workspaces',
  shortcut: 'g ,',
};

export const ALL_NAV: readonly NavItem[] = [OVERVIEW_NAV, ...NAV_GROUPS.flatMap((g) => g.items), SETTINGS_NAV];

export function allNavFor(source: DataSource): NavItem[] {
  return ALL_NAV.filter((n) => source === 'api' || !n.backendOnly);
}

const SUB_PAGES: Record<string, string> = {
  '/community/news': 'News',
  '/community/posts': 'Posts',
  '/community/experts': 'Experts',
  '/community/people': 'People',
};

/** Breadcrumb for the top bar: group › page (› sub-page). */
export function breadcrumbFor(pathname: string): string[] {
  const item = ALL_NAV.find((n) => pathname === n.to || pathname.startsWith(`${n.to}/`));
  if (!item) return ['Not found'];
  const group = NAV_GROUPS.find((g) => g.items.includes(item))?.label;
  const crumbs = [...(group ? [group] : []), item.label];
  const sub = SUB_PAGES[pathname] ?? (/^\/backtests\/[^/]+$/.test(pathname) ? 'Result' : /^\/community\/(experts|people)\/[^/]+$/.test(pathname) ? 'Profile' : undefined);
  return sub ? [...crumbs, sub] : crumbs;
}

/** Shortcut-key → path, for the global hotkey handler. */
export const NAV_SHORTCUTS: Record<string, string> = Object.fromEntries(ALL_NAV.map((n) => [n.shortcut, n.to]));

export function navShortcutsFor(source: DataSource): Record<string, string> {
  return Object.fromEntries(allNavFor(source).map((n) => [n.shortcut, n.to]));
}

/* ------------------------------------------------------------ modules */

/**
 * The seven product modules, presented as one research workflow. The same
 * names are used in the Overview, page eyebrows and the command palette.
 * `status` is honest about what each module runs on today.
 */
export type ModuleState = 'working' | 'simulated' | 'rules' | 'pending';

export interface ProductModule {
  n: string;
  name: string;
  question: string;
  summary: string;
  to: string;
  icon: LucideIcon;
  status: (source: DataSource) => { state: ModuleState; label: string };
}

export const MODULES: readonly ProductModule[] = [
  {
    n: '01',
    name: 'Market intelligence',
    question: 'What is the market doing?',
    summary: 'Sessions, prices across the watchlist and market news with impact tags.',
    to: '/community/news',
    icon: MessagesSquare,
    status: (s) => (s === 'demo' ? { state: 'simulated', label: 'Sample content' } : { state: 'working', label: 'Backend news' }),
  },
  {
    n: '02',
    name: 'Chart analysis',
    question: 'How is price behaving?',
    summary: 'Candles on 15m, 1h and 4h with indicators, a NOW boundary and the model’s levels drawn apart from observed prices.',
    to: '/workspace',
    icon: CandlestickChart,
    status: (s) => (s === 'demo' ? { state: 'simulated', label: 'Simulated prices' } : { state: 'working', label: 'Backend feed' }),
  },
  {
    n: '03',
    name: 'AI research',
    question: 'What does the model see — and why?',
    summary: 'Direction, probability, zones, contributing factors, invalidation conditions and missing data.',
    to: '/workspace',
    icon: Radar,
    status: (s) => (s === 'demo' ? { state: 'simulated', label: 'Demo heuristic' } : { state: 'pending', label: 'Model endpoint pending' }),
  },
  {
    n: '04',
    name: 'Risk management',
    question: 'What does it mean for my capital?',
    summary: 'Position size from your capital and stop, money at risk, and every limit checked before you decide.',
    to: '/risk',
    icon: Scale,
    status: () => ({ state: 'working', label: 'Fully working' }),
  },
  {
    n: '05',
    name: 'Personalised signals',
    question: 'Which setups fit me?',
    summary: 'Model outputs filtered by your saved profile, with each preference and risk check shown.',
    to: '/signals?view=for-you',
    icon: Radar,
    status: (s) => (s === 'demo' ? { state: 'simulated', label: 'Works on simulated outputs' } : { state: 'rules', label: 'Strategy-engine signals; model pending' }),
  },
  {
    n: '06',
    name: 'Performance insights',
    question: 'How reliable has the model been?',
    summary: 'Hit rate, Brier score and calibration over resolved predictions, with every metric defined.',
    to: '/insights',
    icon: Gauge,
    status: (s) => (s === 'demo' ? { state: 'simulated', label: 'Simulated history' } : { state: 'pending', label: 'History endpoint pending' }),
  },
  {
    n: '07',
    name: 'AI assistant',
    question: 'Can I question the evidence?',
    summary: 'Ask about the analysis, its invalidation and your risk — answered only from the data you can see.',
    to: '/assistant',
    icon: Bot,
    status: (s) => (s === 'demo' ? { state: 'rules', label: 'Rule-based demo' } : { state: 'rules', label: 'Rule-based; no AI provider yet' }),
  },
];
