import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { useAuth, useServices } from './contexts';

/**
 * Authentication boundary. In API mode every app route requires a session
 * (the backend protects all APIs — SF17). In demo mode the app is usable
 * without signing in so it can be evaluated immediately.
 *
 * Role-based route gating is intentionally absent: the use-case diagrams that
 * define permissions per role are not available to the web client yet.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { source } = useServices();
  const location = useLocation();
  if (source === 'api' && !session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
