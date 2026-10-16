/**
 * Motion tokens — the single source of truth for timing (docs/MOTION_DESIGN_DIRECTION.md).
 * CSS mirrors these as custom properties in styles/motion.css; keep both in sync.
 *
 * Two registers:
 *  - Interface (fast): controls respond in 120–220ms so the product feels immediate.
 *  - Narrative (cinematic): story sections unfold over 600–1200ms with staggers.
 */
export const DURATION = {
  /** Hover, press, focus. */
  instant: 120,
  /** Toggles, tabs, small state changes. */
  fast: 180,
  /** Dialogs, sheets, menus. */
  base: 260,
  /** Section reveals, cards. */
  slow: 600,
  /** Headline masks, chart drawing, hero staging. */
  cinematic: 1100,
} as const;

export const EASE = {
  /** Default for anything entering: fast start, long settle. */
  out: 'cubic-bezier(0.22, 1, 0.36, 1)',
  /** Things leaving. */
  in: 'cubic-bezier(0.55, 0, 1, 0.45)',
  /** Things moving from one place to another on screen. */
  inOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
  /** A small overshoot for selection feedback only (plan cards). */
  spring: 'cubic-bezier(0.34, 1.4, 0.64, 1)',
} as const;

export const STAGGER = {
  /** Lines of a headline. */
  lines: 110,
  /** Items in a list or grid. */
  items: 70,
  /** Chart candles drawing in. */
  candles: 12,
} as const;

/** Travel distances in px. Mobile uses the `compact` value. */
export const DISTANCE = {
  rise: 18,
  riseCompact: 10,
  parallax: 14,
} as const;

/** Map a 0–1 value through the default "out" curve (cubic-bezier(.22,1,.36,1) approximation). */
export function easeOut(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return 1 - Math.pow(1 - x, 3.2);
}

export function easeInOut(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

/** Sub-range progress: how far `p` is through [start, end], clamped to 0–1. */
export function segment(p: number, start: number, end: number): number {
  if (end <= start) return p >= end ? 1 : 0;
  return Math.min(1, Math.max(0, (p - start) / (end - start)));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Progress of a tall scroll section: 0 when its top reaches the top of the
 * viewport, 1 when its bottom reaches the bottom of the viewport.
 * Pure, so it can be unit-tested without a browser.
 */
export function stickyProgress(top: number, height: number, viewportHeight: number): number {
  const distance = height - viewportHeight;
  if (distance <= 0) return top <= 0 ? 1 : 0;
  return Math.min(1, Math.max(0, -top / distance));
}

/** Index of the active step for `count` equal steps across progress 0–1. */
export function stepAt(p: number, count: number): number {
  return Math.min(count - 1, Math.max(0, Math.floor(p * count)));
}
