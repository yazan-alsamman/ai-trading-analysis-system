/**
 * Minimal in-app event bus (Observer) for cross-page signals that are not
 * worth global state, e.g. "the alert list changed — reload if you show it".
 */
export type AppEvent = 'alerts-changed';

const listeners = new Map<AppEvent, Set<() => void>>();

export const appEvents = {
  emit(event: AppEvent): void {
    listeners.get(event)?.forEach((l) => l());
  },
  on(event: AppEvent, listener: () => void): () => void {
    let set = listeners.get(event);
    if (!set) {
      set = new Set();
      listeners.set(event, set);
    }
    set.add(listener);
    return () => set.delete(listener);
  },
};
