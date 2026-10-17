import { act, cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getInstrument } from '@/domain/instruments';
import { formatMoney, formatUnits } from '@/lib/format';
import { CinematicVideo } from '@/motion/CinematicVideo';
import { renderWithProviders } from '@/test/render';
import { ShowcaseChart } from './components/ShowcaseChart';
import { FOOTAGE } from './media';
import { AssistantScene } from './sections/AssistantScene';
import { ChartToPlanSequence } from './sections/ChartToPlanSequence';
import { RiskSection } from './sections/RiskSection';
import { WorkspaceScene } from './sections/WorkspaceScene';
import { buildShowcase, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from './showcase';

/* ---------------------------------------------------------- test doubles */

const originalMatchMedia = window.matchMedia;
/** Pretend these media queries match (everything else does not). */
function mockMedia(matching: string[]) {
  window.matchMedia = ((query: string) =>
    ({
      matches: matching.some((m) => query.includes(m)),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList) as typeof window.matchMedia;
}

let ioCallbacks: IntersectionObserverCallback[] = [];
class FakeIO {
  constructor(cb: IntersectionObserverCallback) {
    ioCallbacks.push(cb);
  }
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
function intersect(isIntersecting: boolean) {
  act(() => ioCallbacks.forEach((cb) => cb([{ isIntersecting } as IntersectionObserverEntry], {} as IntersectionObserver)));
}

let play: ReturnType<typeof vi.fn>;
let pause: ReturnType<typeof vi.fn>;

beforeEach(() => {
  ioCallbacks = [];
  vi.stubGlobal('IntersectionObserver', FakeIO);
  play = vi.fn(() => Promise.resolve());
  pause = vi.fn();
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(play as unknown as () => Promise<void>);
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause as unknown as () => void);
  vi.spyOn(HTMLMediaElement.prototype, 'paused', 'get').mockReturnValue(false);
});

afterEach(() => {
  cleanup(); // unmount while the media mocks are still installed
  window.matchMedia = originalMatchMedia;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

/* ------------------------------------------------------- CinematicVideo */

describe('CinematicVideo', () => {
  it('renders a muted, looping, inline, decorative video that loads nothing until it nears the viewport', () => {
    const { container } = render(<CinematicVideo {...FOOTAGE.method} />);
    const v = container.querySelector('video');
    expect(v).not.toBeNull();
    expect(v?.muted).toBe(true);
    expect(v?.loop).toBe(true);
    expect(v?.hasAttribute('playsinline')).toBe(true);
    expect(v?.getAttribute('aria-hidden')).toBe('true');
    expect(v?.getAttribute('preload')).toBe('none');
    expect(v?.getAttribute('poster')).toBe(FOOTAGE.method.poster);
    expect(play).not.toHaveBeenCalled();
  });

  it('plays only while on screen and pauses when it leaves', () => {
    const { container } = render(<CinematicVideo {...FOOTAGE.method} />);
    intersect(true);
    expect(play).toHaveBeenCalledTimes(1);
    expect(container.querySelector('video')?.getAttribute('preload')).toBe('auto');
    intersect(false);
    expect(pause).toHaveBeenCalled();
  });

  it('above the fold (priority) it preloads', () => {
    const { container } = render(<CinematicVideo {...FOOTAGE.hero} priority phone="video" />);
    expect(container.querySelector('video')?.getAttribute('preload')).toBe('auto');
  });

  it('shows the still poster only under reduced motion — no video element, no request', () => {
    mockMedia(['prefers-reduced-motion']);
    const { container } = render(<CinematicVideo {...FOOTAGE.hero} priority phone="video" />);
    expect(container.querySelector('video')).toBeNull();
    const img = container.querySelector('img');
    expect(img?.getAttribute('src')).toBe(FOOTAGE.hero.poster);
    expect(img?.getAttribute('alt')).toBe('');
  });

  it('shows the poster when the visitor asked to save data', () => {
    Object.defineProperty(navigator, 'connection', { value: { saveData: true }, configurable: true });
    try {
      const { container } = render(<CinematicVideo {...FOOTAGE.closing} />);
      expect(container.querySelector('video')).toBeNull();
      expect(container.querySelector('img')).not.toBeNull();
    } finally {
      delete (navigator as Navigator & { connection?: unknown }).connection;
    }
  });

  it('on phones: secondary scenes show the poster, the hero plays its small rendition', () => {
    mockMedia(['max-width: 47.99rem']);
    const secondary = render(<CinematicVideo {...FOOTAGE.assistant} />);
    expect(secondary.container.querySelector('video')).toBeNull();
    const hero = render(<CinematicVideo {...FOOTAGE.hero} priority phone="video" />);
    expect(hero.container.querySelector('video')?.getAttribute('src')).toBe(FOOTAGE.hero.srcSmall);
  });

  it('falls back to the poster when playback is refused', async () => {
    play.mockImplementation(() => Promise.reject(new Error('NotAllowedError')));
    const { container } = render(<CinematicVideo {...FOOTAGE.method} />);
    intersect(true);
    await act(async () => {
      await Promise.resolve();
    });
    expect(container.querySelector('video')).toBeNull();
    expect(container.querySelector('img')?.getAttribute('src')).toBe(FOOTAGE.method.poster);
  });

  it('every footage entry names its source, licence and a local file (no hotlinking)', () => {
    for (const f of Object.values(FOOTAGE)) {
      expect(f.src).toMatch(/^\/media\/.+\.mp4$/);
      expect(f.poster).toMatch(/^\/media\/.+\.webp$/);
      expect(f.licence).toMatch(/commercial use/);
      expect(['Coverr', 'Mixkit']).toContain(f.source);
    }
  });
});

/* ------------------------------------------------------- chart and scenes */

describe('hero chart ambient scan', () => {
  const s = buildShowcase();
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const chart = (scan: boolean) => (
    <ShowcaseChart candles={s.candles} opportunity={s.opportunity} timeframe={SHOWCASE_TIMEFRAME} precision={inst.pricePrecision} label="chart" scan={scan} />
  );

  it('starts after the intro, labels its readout as simulated, and stops when switched off', () => {
    vi.useFakeTimers();
    const { container, rerender } = render(chart(true));
    expect(container.textContent).not.toMatch(/simulated/);
    act(() => vi.advanceTimersByTime(3700));
    expect(container.textContent).toMatch(/UTC · O .* C .* · simulated/);
    rerender(chart(false));
    expect(container.textContent).not.toMatch(/· simulated/);
  });

  it('never scans when not asked to', () => {
    vi.useFakeTimers();
    const { container } = render(chart(false));
    act(() => vi.advanceTimersByTime(10_000));
    expect(container.textContent).not.toMatch(/· simulated/);
  });
});

describe('scenes', () => {
  it('workspace: the 3D device is decorative and described in text with the showcase numbers', () => {
    renderWithProviders(<WorkspaceScene />);
    const s = buildShowcase();
    expect(screen.getByTestId('laptop').closest('[aria-hidden="true"]')).not.toBeNull();
    expect(screen.getByText(/Illustration: the research workspace on a laptop/)).toHaveTextContent(formatMoney(s.risk.monetaryRisk, 'USD'));
  });

  it('chart → plan ends in a structured research plan, labelled simulated and not advice', () => {
    renderWithProviders(<ChartToPlanSequence />);
    const plan = screen.getByRole('article', { name: /Structured research plan/ });
    for (const term of ['Thesis', 'Levels', 'Size', 'Checks', 'Invalidated if', 'Missing']) expect(within(plan).getByText(term)).toBeInTheDocument();
    expect(plan).toHaveTextContent('Research, not advice');
    expect(within(plan).getByText('Simulated')).toBeInTheDocument();
  });

  it('risk: the cause → effect chain is consistent with the sized position', () => {
    renderWithProviders(<RiskSection />);
    const s = buildShowcase();
    const chain = screen.getByRole('list', { name: 'How the position size follows' });
    expect(chain).toHaveTextContent(formatMoney(s.risk.riskBudget, 'USD'));
    expect(chain).toHaveTextContent(formatUnits(s.risk.units, getInstrument(SHOWCASE_SYMBOL).base));
    expect(s.risk.riskBudget / s.risk.stopDistance).toBeCloseTo(s.risk.units, 6);
  });

  it('assistant: stays labelled as a rule-based demo and shows the context it used', () => {
    renderWithProviders(<AssistantScene />);
    expect(screen.getByText('Rule-based demo')).toBeInTheDocument();
    expect(screen.getByText(/Rule-based, not a language model/)).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Context the answer used' }).children.length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/GPT|Claude|LLM-powered|large language model answers/i);
  });
});
