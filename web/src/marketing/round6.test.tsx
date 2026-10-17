import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RouteObject } from 'react-router';
import { router } from '@/app/router';
import { APP_STORES, isSafeExternalUrl, SOCIAL_LINKS } from '@/config/externalLinks';
import { EMPTY_CONTEXT, PROMPT_GROUPS, REPLY_KINDS, SUGGESTED_PROMPTS, type ReplyKind } from '@/domain/assistant';
import { splitSimulatedNote } from '@/features/assistant/replyText';
import { composeReply } from '@/services/demo/assistant';
import { renderWithProviders } from '@/test/render';
import { createShowcaseAssistant, PUBLIC_THREAD_KEY, showcaseContext } from './assistant/showcaseAssistant';
import { PublicAssistant } from './assistant/PublicAssistant';
import { FOOTER_GROUPS, PUBLIC_NAV } from './content';
import { PublicFooter } from './layout/PublicFooter';
import { AboutPage } from './pages/AboutPage';
import { DataStoragePage, RiskDisclosurePage } from './pages/LegalPages';
import { buildShowcase } from './showcase';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** Every concrete path the router knows. */
function routePaths(routes: readonly RouteObject[], prefix = ''): string[] {
  return routes.flatMap((r) => {
    const here = r.index ? prefix || '/' : r.path ? (r.path.startsWith('/') ? r.path : `${prefix.replace(/\/$/, '')}/${r.path}`) : prefix;
    return [...(r.path || r.index ? [here] : []), ...(r.children ? routePaths(r.children, here) : [])];
  });
}

describe('footer and navigation destinations', () => {
  const paths = new Set(routePaths(router.routes));

  it('every footer and header link points at a route that exists (no dead links)', () => {
    const links = [...FOOTER_GROUPS.flatMap((g) => g.links.map((l) => l.to)), ...PUBLIC_NAV.map((n) => n.to)];
    for (const to of links) {
      const path = to.split('#')[0] || '/';
      expect(paths.has(path), `${to} → ${path}`).toBe(true);
    }
  });

  it('never invents a store listing or a social profile', () => {
    // Nothing is published yet: the configuration must say so rather than guess.
    for (const s of APP_STORES) expect(s.url).toBeNull();
    expect(SOCIAL_LINKS).toHaveLength(0);
    expect(isSafeExternalUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeExternalUrl('https://example.org')).toBe(true);
  });

  it('renders the honest unavailable states and no external links', () => {
    renderWithProviders(<PublicFooter />);
    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByText('Download the app')).toBeInTheDocument();
    expect(within(footer).getAllByText(/coming soon/i)).toHaveLength(2);
    expect(within(footer).getByText(/Social channels: none announced yet/)).toBeInTheDocument();
    expect(within(footer).getByText(/Terms of service and privacy policy: in preparation/)).toBeInTheDocument();
    expect(footer.querySelectorAll('a[href^="http"]')).toHaveLength(0);
    expect(footer.querySelectorAll('a[href="#"], a:not([href])')).toHaveLength(0);
    expect(within(footer).getByText(/licensed stock video from Coverr and Mixkit/)).toBeInTheDocument();
    expect(within(footer).getByRole('link', { name: 'Read the full risk disclosure' })).toHaveAttribute('href', '/legal/risk-disclosure');
  });
});

describe('assistant: structured replies', () => {
  it('classifies each demo answer and every follow-up is a real suggested prompt', () => {
    const ctx = showcaseContext(true);
    const now = buildShowcase().opportunity.generatedAt;
    const kinds: Record<string, ReplyKind> = {
      'Explain the current analysis': 'explain',
      'What would invalidate this projection?': 'invalidate',
      'Calculate the risk for my capital and stop-loss': 'risk',
      'What information is missing before I can evaluate this?': 'missing',
      'What is a Brier score?': 'glossary',
      'Tell me a joke': 'unknown',
    };
    for (const [q, k] of Object.entries(kinds)) expect(composeReply(q, ctx, now).kind).toBe(k);
    for (const meta of Object.values(REPLY_KINDS)) for (const p of meta.next) expect(SUGGESTED_PROMPTS).toContain(p);
    for (const g of PROMPT_GROUPS) for (const p of g.prompts) expect(SUGGESTED_PROMPTS).toContain(p);
  });

  it('separates the simulated-data note from the answer body', () => {
    const r = composeReply('Explain the current analysis', showcaseContext(false), buildShowcase().opportunity.generatedAt);
    const { body, note } = splitSimulatedNote(r.content);
    expect(note).toMatch(/demo heuristic/);
    expect(body).not.toMatch(/Simulated data:/);
    expect(splitSimulatedNote('plain answer')).toEqual({ body: 'plain answer', note: null });
  });

  it('the showcase assistant is the rule-based demo, answers at the example time, and can be cancelled', async () => {
    const svc = createShowcaseAssistant(5);
    expect(svc.describe().provider).toBe('demo-rules');
    const ctx = showcaseContext(false);
    const reply = await svc.reply([{ id: '1', role: 'user', content: 'What would invalidate this projection?', createdAt: 0 }], ctx);
    expect(reply.createdAt).toBe(buildShowcase().opportunity.generatedAt);
    expect(reply.content).not.toMatch(/has expired|is stale/i);
    const ctrl = new AbortController();
    const pending = svc.reply([{ id: '2', role: 'user', content: 'Explain the current analysis', createdAt: 0 }], ctx, { signal: ctrl.signal });
    ctrl.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(showcaseContext(false).riskProfile).toBeNull();
    expect(showcaseContext(true).riskProfile?.capital).toBe(25_000);
    expect(EMPTY_CONTEXT.opportunity).toBeNull();
  });

  it('public assistant: suggested prompt → labelled reply card with next steps; Enter sends; clear empties', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PublicAssistant />);
    expect(screen.getByText('Rule-based demo')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Risk' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'What would invalidate this projection?' }));
    const card = await screen.findByRole('article', { name: 'Assistant answer: Invalidation conditions' }, { timeout: 3000 });
    expect(within(card).getByText(/rule-based, not a language model/)).toBeInTheDocument();
    expect(within(card).getByText('Next research step:')).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(PUBLIC_THREAD_KEY) ?? '[]')).toHaveLength(2);
    // Enter sends; the thread stays in chronological order.
    await user.type(screen.getByRole('textbox', { name: 'Ask the assistant' }), 'What is a Brier score?{Enter}');
    await screen.findByRole('article', { name: 'Assistant answer: Definition' }, { timeout: 3000 });
    const answers = screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'));
    expect(answers).toEqual(['Assistant answer: Invalidation conditions', 'Assistant answer: Definition']);
    await user.click(screen.getByRole('button', { name: 'Clear conversation' }));
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(localStorage.getItem(PUBLIC_THREAD_KEY)).toBeNull();
  });
});

describe('about and legal pages', () => {
  it('about: answers the eight questions in order, with honest status labels', () => {
    const io = vi.fn(() => ({ observe: vi.fn(), disconnect: vi.fn(), unobserve: vi.fn() }));
    vi.stubGlobal('IntersectionObserver', io);
    try {
      renderWithProviders(<AboutPage />, { route: '/about' });
      const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/A clearer way\s*to read the markets/);
      expect(headings.join(' | ')).toMatch(/organised.*one workflow.*decision you can explain.*don’t know.*We show it.*do the reading.*This is the process/);
      // Capability status uses the shared vocabulary; nothing planned is presented as working.
      expect(screen.getAllByText('Demo data').length).toBeGreaterThan(0);
      expect(screen.getByText('Works now')).toBeInTheDocument();
      expect(screen.getByText('Needs backend')).toBeInTheDocument();
      expect(screen.getByText(/rule-based demo, and it says so/)).toBeInTheDocument();
      expect(screen.getByText(/No verified live results exist yet/)).toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(/testimonial|founded in|award|regulated by|win rate of \d/i);
      for (const name of ['Explore the platform', 'View membership', 'Create an account']) expect(screen.getAllByRole('link', { name: new RegExp(name) }).length).toBeGreaterThan(0);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('legal pages state limits plainly and list the real storage keys', () => {
    renderWithProviders(<RiskDisclosurePage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Risk disclosure' })).toBeInTheDocument();
    expect(screen.getByText(/has not been reviewed as a legal document/)).toBeInTheDocument();
    cleanup();
    renderWithProviders(<DataStoragePage />);
    const table = screen.getByRole('table');
    for (const key of ['ata.preferences.v1', 'ata.session.v1', 'ata.assistant.public.v1', 'ata.membership.selected.v1']) expect(within(table).getByText(key)).toBeInTheDocument();
    expect(screen.getByText(/sets no cookies/)).toBeInTheDocument();
  });
});

describe('launcher', () => {
  it('is not rendered outside the story pages', async () => {
    const { AssistantLauncher } = await import('./assistant/AssistantLauncher');
    renderWithProviders(<AssistantLauncher />, { route: '/membership' });
    expect(screen.queryByRole('button', { name: /Ask the research assistant/ })).toBeNull();
    cleanup();
    renderWithProviders(<AssistantLauncher />, { route: '/about' });
    // Present but hidden until the visitor scrolls past the hero.
    const btn = screen.getByText('Ask the research assistant').closest('button');
    expect(btn).toHaveAttribute('aria-hidden', 'true');
    await act(async () => undefined);
  });
});
