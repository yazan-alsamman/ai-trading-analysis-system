import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';
import type { Preferences, Workspace } from '@/domain/preferences';
import type { Session } from '@/domain/user';
import { localId } from '@/lib/cn';
import { resolveTimeZone } from '@/lib/format';
import { readStored, removeStored, writeStored } from '@/lib/storage';
import { createServices } from '@/services';
import { config } from '@/services/config';
import { SessionSchema } from '@/services/schemas';
import type { Services } from '@/services/types';
import { AuthContext, PreferencesContext, ServicesContext, type AuthApi, type PreferencesApi } from './contexts';
import { DEFAULT_PREFERENCES, defaultWorkspace, isSupportedTimeZone, PREFERENCES_KEY, PreferencesSchema } from './preferencesStore';
import { ToastProvider } from './ToastProvider';

const SESSION_KEY = 'ata.session.v1';

/* ------------------------------------------------------------ helpers */

function subscribeColorScheme(onChange: () => void) {
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', onChange);
  return () => mq.removeEventListener('change', onChange);
}
const systemPrefersDark = () => window.matchMedia('(prefers-color-scheme: dark)').matches;

function loadPreferences(): Preferences {
  const stored = readStored(PREFERENCES_KEY, PreferencesSchema, DEFAULT_PREFERENCES);
  return isSupportedTimeZone(stored.timeZone) ? stored : { ...stored, timeZone: 'UTC' };
}

/* --------------------------------------------------------- providers */

function PreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences);
  const systemDark = useSyncExternalStore(subscribeColorScheme, systemPrefersDark, () => true);
  const resolvedTheme = prefs.theme === 'system' ? (systemDark ? 'dark' : 'light') : prefs.theme;

  useEffect(() => writeStored(PREFERENCES_KEY, prefs), [prefs]);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolvedTheme;
    root.dataset.density = prefs.density;
  }, [resolvedTheme, prefs.density]);

  const update = useCallback((fn: (p: Preferences) => Preferences) => setPrefs(fn), []);

  const api = useMemo<PreferencesApi>(() => {
    const activeWorkspace = prefs.workspaces.find((w) => w.id === prefs.activeWorkspaceId) ?? prefs.workspaces[0] ?? defaultWorkspace();
    return {
      prefs,
      resolvedTheme,
      timeZone: resolveTimeZone(prefs.timeZone),
      activeWorkspace,
      setTheme: (theme) => update((p) => ({ ...p, theme })),
      setDensity: (density) => update((p) => ({ ...p, density })),
      setTimeZone: (timeZone) => update((p) => ({ ...p, timeZone })),
      setChannels: (channels) => update((p) => ({ ...p, channels })),
      updateWorkspace: (patch, id) =>
        update((p) => {
          const target = id ?? p.activeWorkspaceId;
          return { ...p, workspaces: p.workspaces.map((w) => (w.id === target ? { ...w, ...patch } : w)) };
        }),
      createWorkspace: (name) => {
        // New workspaces start from the current layout so switching feels continuous.
        const ws: Workspace = { ...activeWorkspace, id: localId('ws'), name };
        update((p) => ({ ...p, workspaces: [...p.workspaces, ws], activeWorkspaceId: ws.id }));
        return ws;
      },
      deleteWorkspace: (id) =>
        update((p) => {
          if (p.workspaces.length <= 1) return p;
          const workspaces = p.workspaces.filter((w) => w.id !== id);
          const activeWorkspaceId = p.activeWorkspaceId === id ? (workspaces[0]?.id ?? p.activeWorkspaceId) : p.activeWorkspaceId;
          return { ...p, workspaces, activeWorkspaceId };
        }),
      setActiveWorkspace: (id) => update((p) => (p.workspaces.some((w) => w.id === id) ? { ...p, activeWorkspaceId: id } : p)),
      setRiskProfile: (riskProfile) => update((p) => ({ ...p, riskProfile })),
      setSignalProfile: (signalProfile) => update((p) => ({ ...p, signalProfile })),
    };
  }, [prefs, resolvedTheme, update]);

  return <PreferencesContext.Provider value={api}>{children}</PreferencesContext.Provider>;
}

/**
 * Creates the service layer once and wires authentication into it.
 * `services` can be injected (tests).
 */
const readSession = () => readStored(SESSION_KEY, SessionSchema.nullable(), null);

function DataAndAuthProvider({ children, services: injected }: { children: ReactNode; services?: Services }) {
  const [session, setSessionState] = useState<Session | null>(readSession);
  const sessionRef = useRef(session);

  /**
   * Persist synchronously: rotated refresh tokens must be visible to other tabs
   * immediately (the backend revokes every session when an old one is reused).
   */
  const setSession = useCallback((next: Session | null) => {
    sessionRef.current = next;
    if (next) writeStored(SESSION_KEY, next);
    else removeStored(SESSION_KEY);
    setSessionState(next);
  }, []);

  const [services] = useState<Services>(
    () =>
      injected ??
      createServices(config, { get: () => sessionRef.current, set: setSession, readPersisted: readSession }, () => setSession(null)),
  );

  // Another tab signed in, refreshed its token or signed out.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== SESSION_KEY) return;
      const next = readSession();
      sessionRef.current = next;
      setSessionState(next);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // A stored backend session is validated once on start-up (refreshing the token if needed).
  const [status, setStatus] = useState<AuthApi['status']>(() => (services.source === 'api' && sessionRef.current && !sessionRef.current.isDemo ? 'restoring' : 'ready'));
  useEffect(() => {
    if (status !== 'restoring') return;
    const ctrl = new AbortController();
    services.account
      .getProfile({ signal: ctrl.signal })
      .then((user) => {
        const current = sessionRef.current;
        if (current) setSession({ ...current, user });
      })
      // 401 (after a failed refresh) has already ended the session; offline keeps it until the server can decide.
      .catch(() => undefined)
      .finally(() => !ctrl.signal.aborted && setStatus('ready'));
    return () => ctrl.abort();
  }, [services, status, setSession]);

  const auth = useMemo<AuthApi>(
    () => ({
      session,
      status,
      login: async (input) => setSession(await services.auth.login(input)),
      register: async (input) => setSession(await services.auth.register(input)),
      logout: async () => {
        const current = sessionRef.current;
        setSession(null);
        // Account-specific data must not be shown to the next person on this browser.
        if (services.source === 'api') removeStored('ata.assistant.thread.v1');
        if (current) await services.auth.logout(current).catch(() => undefined);
      },
      updateUser: (user) => {
        const current = sessionRef.current;
        if (current) setSession({ ...current, user });
      },
    }),
    [services, session, status, setSession],
  );

  return (
    <ServicesContext.Provider value={services}>
      <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
    </ServicesContext.Provider>
  );
}

export function AppProviders({ children, services }: { children: ReactNode; services?: Services }) {
  return (
    <PreferencesProvider>
      <DataAndAuthProvider {...(services ? { services } : {})}>
        <ToastProvider>{children}</ToastProvider>
      </DataAndAuthProvider>
    </PreferencesProvider>
  );
}
