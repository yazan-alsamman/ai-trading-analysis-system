import { useEffect, useRef } from 'react';

/**
 * Single-key and two-key ("g w") shortcuts. Ignored while typing in a field or
 * when a modal dialog is open, and never bound to Ctrl/Meta/Alt combinations
 * (those belong to the browser and assistive technology).
 */
export type HotkeyMap = Record<string, () => void>;

const CHORD_TIMEOUT_MS = 1000;

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

export function useHotkeys(bindings: HotkeyMap, enabled = true): void {
  const ref = useRef(bindings);
  ref.current = bindings;

  useEffect(() => {
    if (!enabled) return;
    let pending: string | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return;
      if (document.querySelector('dialog[open]')) return;
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      const map = ref.current;

      if (pending) {
        const action = map[`${pending} ${key}`];
        pending = null;
        clearTimeout(timer);
        if (action) {
          e.preventDefault();
          action();
        }
        return;
      }
      if (Object.keys(map).some((k) => k.startsWith(`${key} `))) {
        pending = key;
        timer = setTimeout(() => (pending = null), CHORD_TIMEOUT_MS);
        return;
      }
      const action = map[key === '?' ? '?' : key];
      if (action) {
        e.preventDefault();
        action();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      clearTimeout(timer);
    };
  }, [enabled]);
}
