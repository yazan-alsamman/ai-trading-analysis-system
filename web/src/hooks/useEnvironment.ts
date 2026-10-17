import { useEffect, useState, useSyncExternalStore } from 'react';
import { demoScenario, type DemoScenario } from '@/services/demo/scenario';

function subscribeOnline(onChange: () => void) {
  window.addEventListener('online', onChange);
  window.addEventListener('offline', onChange);
  return () => {
    window.removeEventListener('online', onChange);
    window.removeEventListener('offline', onChange);
  };
}

/** Browser connectivity (SF19 offline handling). */
export function useOnlineStatus(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
}

/** Current time, refreshed on an interval — for relative timestamps and staleness. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function useDemoScenario(): [DemoScenario, (s: DemoScenario) => void] {
  const value = useSyncExternalStore(demoScenario.subscribe, demoScenario.get, demoScenario.get);
  return [value, demoScenario.set];
}

/** Matches a CSS media query, e.g. '(min-width: 80rem)'. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener('change', onChange);
      return () => mq.removeEventListener('change', onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
