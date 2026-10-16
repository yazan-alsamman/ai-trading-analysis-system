import { useEffect, useRef, useState, useSyncExternalStore, type RefObject } from 'react';
import { stepAt, stickyProgress } from './tokens';

/* ------------------------------------------------------------ media */

function mediaStore(query: string) {
  return {
    subscribe(cb: () => void) {
      if (typeof window === 'undefined' || !window.matchMedia) return () => undefined;
      const mq = window.matchMedia(query);
      mq.addEventListener('change', cb);
      return () => mq.removeEventListener('change', cb);
    },
    get(): boolean {
      return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(query).matches;
    },
  };
}

const reduced = mediaStore('(prefers-reduced-motion: reduce)');
// Pinned, scroll-scrubbed sequences: wide screens only (touch tablets and phones get static layouts).
const cinematic = mediaStore('(min-width: 64rem) and (min-height: 600px)');
const finePointer = mediaStore('(hover: hover) and (pointer: fine)');

export function useReducedMotion(): boolean {
  return useSyncExternalStore(reduced.subscribe, reduced.get, () => false);
}

/** True when scroll-scrubbed, pinned storytelling should run. */
export function useCinematic(): boolean {
  const r = useReducedMotion();
  const wide = useSyncExternalStore(cinematic.subscribe, cinematic.get, () => false);
  return wide && !r;
}

export function useFinePointer(): boolean {
  return useSyncExternalStore(finePointer.subscribe, finePointer.get, () => false);
}

/* ----------------------------------------------------- scroll manager */

/**
 * One passive scroll/resize listener for the whole app, coalesced to one
 * animation frame. Sections subscribe only while they are on screen.
 */
type FrameListener = () => void;
const frameListeners = new Set<FrameListener>();
let rafId = 0;

function schedule() {
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0;
    frameListeners.forEach((l) => l());
  });
}

export function subscribeFrames(listener: FrameListener): () => void {
  if (frameListeners.size === 0) {
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule, { passive: true });
  }
  frameListeners.add(listener);
  schedule();
  return () => {
    frameListeners.delete(listener);
    if (frameListeners.size === 0) {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
    }
  };
}

/** Number of active scroll subscribers (diagnostics and tests). */
export function activeFrameListeners(): number {
  return frameListeners.size;
}

/* ------------------------------------------------------------ in view */

/**
 * True once the element has entered the viewport (or immediately when
 * IntersectionObserver is missing or motion is reduced — content is never
 * hidden behind an observer that cannot fire).
 */
export function useInView<T extends Element>(ref: RefObject<T | null>, options: { once?: boolean; rootMargin?: string; threshold?: number } = {}): boolean {
  const { once = true, rootMargin = '0px 0px -12% 0px', threshold = 0.15 } = options;
  const r = useReducedMotion();
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || r || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setSeen(true);
            if (once) io.disconnect();
          } else if (!once) setSeen(false);
        }
      },
      { rootMargin, threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, once, rootMargin, threshold, r]);
  return r || typeof IntersectionObserver === 'undefined' ? true : seen;
}

/* -------------------------------------------------- scroll progress */

/**
 * Calls `onFrame(progress)` on animation frames while the (tall) element is
 * on screen; progress runs 0 → 1 across its pinned scroll distance. Writes
 * happen in the callback (DOM/CSS variables), not through React state.
 */
export function useScrollProgress<T extends HTMLElement>(ref: RefObject<T | null>, onFrame: (p: number) => void, enabled: boolean): void {
  const cb = useRef(onFrame);
  cb.current = onFrame;
  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;
    let unsubscribe: (() => void) | null = null;
    const tick = () => {
      const rect = el.getBoundingClientRect();
      cb.current(stickyProgress(rect.top, rect.height, window.innerHeight));
    };
    const start = () => {
      if (!unsubscribe) unsubscribe = subscribeFrames(tick);
    };
    const stop = () => {
      unsubscribe?.();
      unsubscribe = null;
    };
    if (typeof IntersectionObserver === 'undefined') {
      start();
      return stop;
    }
    const io = new IntersectionObserver((entries) => entries.forEach((e) => (e.isIntersecting ? start() : stop())), { rootMargin: '10% 0px' });
    io.observe(el);
    return () => {
      io.disconnect();
      stop();
    };
  }, [ref, enabled]);
}

/**
 * Pinned-sequence helper: writes `--p` on the element every frame and returns
 * the active step (React re-renders only when the step changes).
 */
export function useStepProgress<T extends HTMLElement>(ref: RefObject<T | null>, steps: number, enabled: boolean): number {
  const [step, setStep] = useState(0);
  useScrollProgress(
    ref,
    (p) => {
      ref.current?.style.setProperty('--p', p.toFixed(4));
      const s = stepAt(p, steps);
      setStep((prev) => (prev === s ? prev : s));
    },
    enabled,
  );
  return step;
}

/* ---------------------------------------------------- pointer parallax */

/**
 * Writes `--px` / `--py` (−1…1) on the element from the pointer position,
 * once per frame. Fine pointers only; disabled under reduced motion.
 */
export function usePointerParallax<T extends HTMLElement>(ref: RefObject<T | null>, enabled: boolean): void {
  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;
    let raf = 0;
    let x = 0;
    let y = 0;
    const apply = () => {
      raf = 0;
      el.style.setProperty('--px', x.toFixed(3));
      el.style.setProperty('--py', y.toFixed(3));
    };
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      x = ((e.clientX - r.left) / r.width) * 2 - 1;
      y = ((e.clientY - r.top) / r.height) * 2 - 1;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    const leave = () => {
      x = 0;
      y = 0;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
      if (raf) cancelAnimationFrame(raf);
      el.style.removeProperty('--px');
      el.style.removeProperty('--py');
    };
  }, [ref, enabled]);
}
