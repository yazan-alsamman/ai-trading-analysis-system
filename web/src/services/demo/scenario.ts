import { ApiError } from '../errors';

/**
 * Demo-only switch that makes the simulated services behave like a slow,
 * failing or interrupted backend, so every interface state can be inspected
 * (Settings → Demo controls). Has no effect in API mode.
 */
export type DemoScenario = 'normal' | 'slow' | 'errors' | 'feed_interrupted' | 'empty';

export const DEMO_SCENARIOS: readonly { id: DemoScenario; label: string; description: string }[] = [
  { id: 'normal', label: 'Normal', description: 'Simulated data loads quickly and the price feed updates every second.' },
  { id: 'slow', label: 'Slow network', description: 'Every request takes about 3 seconds — shows loading states.' },
  { id: 'errors', label: 'Request failures', description: 'Data requests fail — shows error states and retry.' },
  { id: 'feed_interrupted', label: 'Feed interrupted', description: 'Price updates stop — the feed becomes stale after 10 seconds.' },
  { id: 'empty', label: 'Empty data', description: 'Lists return no items — shows empty states.' },
];

let current: DemoScenario = 'normal';
const listeners = new Set<() => void>();

export const demoScenario = {
  get: (): DemoScenario => current,
  set(next: DemoScenario) {
    current = next;
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

/** Simulated network latency that respects cancellation and the active scenario. */
export function simulateRequest(signal?: AbortSignal, baseMs = 220): Promise<void> {
  const scenario = current;
  const delay = scenario === 'slow' ? 3000 : baseMs + Math.random() * 180;
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new ApiError('aborted', 'Request cancelled'));
    const timer = setTimeout(() => {
      if (scenario === 'errors') reject(new ApiError('server', 'Simulated server error (demo scenario)', { status: 503 }));
      else resolve();
    }, delay);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new ApiError('aborted', 'Request cancelled'));
      },
      { once: true },
    );
  });
}

/** Lists honour the "empty" scenario. */
export function demoList<T>(items: T[]): T[] {
  return current === 'empty' ? [] : items;
}
