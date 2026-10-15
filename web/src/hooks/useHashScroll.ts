import { useEffect } from 'react';
import { useLocation } from 'react-router';

/** Scroll to `#id` after navigation (the router does not do this for SPA links). */
export function useHashScroll(ready = true): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (!ready || !hash) return;
    const el = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!el) return;
    el.scrollIntoView({ block: 'start' });
    // Move focus for keyboard and screen-reader users without a second scroll.
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
  }, [hash, ready]);
}
