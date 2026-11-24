import type { Session } from '@/domain/user';
import { isApiError } from '../errors';
import { TokenPairSchema } from '../schemas';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';

/** Where the session lives. `set` must persist synchronously so other tabs see rotated tokens at once. */
export interface SessionStore {
  get(): Session | null;
  set(session: Session | null): void;
  /** The session as currently persisted (possibly updated by another tab). */
  readPersisted(): Session | null;
}

export interface TokenManager {
  /** The access token to send now, refreshed first when it expires within `earlyMs`. */
  getToken(): Promise<string | undefined>;
  /** Rotate the refresh token. Resolves undefined (and ends the session) if the server refuses. */
  refresh(): Promise<string | undefined>;
}

const LOCK = 'ata-auth-refresh';

/**
 * Access/refresh token handling for the FastAPI backend (backend/app/services/auth_service.py).
 *
 * The backend ROTATES refresh tokens and treats a reused one as theft, revoking
 * every session of the user. So:
 *  - refreshes are single-flight within a tab (concurrent 401s share one call);
 *  - across tabs they run under a Web Lock, and inside it the persisted session
 *    is re-read: if another tab already rotated the token, it is adopted instead
 *    of presenting the old (now revoked) refresh token;
 *  - a network failure does not end the session (the error propagates); only a
 *    401/400 from /auth/refresh does.
 */
export function createTokenManager(http: HttpClient, store: SessionStore, earlyMs = 60_000): TokenManager {
  let inflight: Promise<string | undefined> | null = null;

  const rotate = async (): Promise<string | undefined> => {
    const current = store.get();
    if (!current?.refreshToken) return undefined;
    const persisted = store.readPersisted();
    if (persisted?.refreshToken && persisted.refreshToken !== current.refreshToken && (persisted.expiresAt ?? 0) > Date.now() + 5_000) {
      store.set(persisted);
      return persisted.token;
    }
    try {
      const tokens = await http.request('POST', endpoints.auth.refresh, {
        body: { refresh_token: current.refreshToken },
        schema: TokenPairSchema,
        token: null,
        authFailureHandled: true,
      });
      const latest = store.get() ?? current;
      store.set({ ...latest, token: tokens.access_token, refreshToken: tokens.refresh_token, expiresAt: Date.now() + tokens.expires_in * 1000 });
      return tokens.access_token;
    } catch (e) {
      if (isApiError(e) && (e.kind === 'unauthorized' || e.kind === 'validation' || e.kind === 'forbidden')) {
        store.set(null);
        return undefined;
      }
      throw e;
    }
  };

  const refresh = (): Promise<string | undefined> => {
    if (!inflight) {
      const locks = typeof navigator !== 'undefined' ? (navigator as Navigator & { locks?: LockManager }).locks : undefined;
      const run = locks ? async () => await locks.request(LOCK, rotate) : rotate;
      inflight = run().finally(() => {
        inflight = null;
      });
    }
    return inflight;
  };

  return {
    refresh,
    async getToken() {
      const s = store.get();
      if (!s?.token) return undefined;
      if (s.refreshToken && s.expiresAt !== undefined && s.expiresAt - Date.now() < earlyMs) {
        try {
          return (await refresh()) ?? undefined;
        } catch (e) {
          // Offline: try the current token; the server decides.
          if (isApiError(e) && (e.kind === 'network' || e.kind === 'timeout')) return s.token;
          throw e;
        }
      }
      return s.token;
    },
  };
}

/** Only same-origin, in-app paths are accepted as post-sign-in destinations (no open redirects). */
export function safeRedirect(target: unknown, fallback = '/overview'): string {
  if (typeof target !== 'string') return fallback;
  if (!target.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) return fallback;
  if (/^\/(login|register)\b/.test(target)) return fallback;
  return target;
}

