import { useCallback, useEffect, useRef, useState } from 'react';
import { isAbort } from '@/services/errors';

export type ResourceStatus = 'loading' | 'success' | 'error';

export interface Resource<T> {
  status: ResourceStatus;
  data: T | undefined;
  error: unknown;
  /** True while re-fetching with previous data still shown (the "updating" state). */
  isRefreshing: boolean;
  reload: () => void;
  /** Replace data locally after a successful mutation. */
  setData: (updater: (prev: T | undefined) => T) => void;
}

interface State<T> {
  key: string;
  status: ResourceStatus;
  data: T | undefined;
  error: unknown;
  isRefreshing: boolean;
}

/**
 * Loads async data keyed by `key`.
 *  - Changing `key` (e.g. a different instrument) clears data → loading state,
 *    so old data is never shown under a new label.
 *  - `reload()` keeps current data visible while refreshing.
 *  - In-flight requests are aborted on key change/unmount, so late responses
 *    can never overwrite newer ones.
 */
export function useResource<T>(key: string, loader: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [reloadToken, setReloadToken] = useState(0);
  const [state, setState] = useState<State<T>>({ key, status: 'loading', data: undefined, error: undefined, isRefreshing: false });

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) =>
      prev.key === key && prev.data !== undefined
        ? { ...prev, isRefreshing: true, error: undefined }
        : { key, status: 'loading', data: undefined, error: undefined, isRefreshing: false },
    );
    loaderRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, status: 'success', data, error: undefined, isRefreshing: false });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setState((prev) => ({
          key,
          status: 'error',
          // Keep stale data on refresh failure so the UI can show "partial failure".
          data: prev.key === key ? prev.data : undefined,
          error,
          isRefreshing: false,
        }));
      });
    return () => controller.abort();
  }, [key, reloadToken]);

  const reload = useCallback(() => setReloadToken((t) => t + 1), []);
  const setData = useCallback(
    (updater: (prev: T | undefined) => T) => setState((prev) => ({ ...prev, status: 'success', data: updater(prev.data) })),
    [],
  );

  // While the effect for a new key has not run yet, report loading for that key.
  if (state.key !== key) {
    return { status: 'loading', data: undefined, error: undefined, isRefreshing: false, reload, setData };
  }
  return { status: state.status, data: state.data, error: state.error, isRefreshing: state.isRefreshing, reload, setData };
}
