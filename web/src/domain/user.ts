/** Actors from the project description. Permissions per role are defined by the
 *  use-case diagrams, which the web client does not yet have — so the UI does not
 *  gate navigation by role. See docs/KNOWN_ISSUES.md. */
export type UserRole = 'trader' | 'analyst' | 'expert' | 'admin';

export const ROLE_LABELS: Record<UserRole, string> = {
  trader: 'Trader',
  analyst: 'Analyst',
  expert: 'Expert',
  admin: 'Admin',
};

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface Session {
  user: User;
  /** Bearer (access) token issued by the backend. Absent for demo sessions. */
  token?: string;
  /** Refresh token — sent to /auth/logout so the server can revoke it. */
  refreshToken?: string;
  /** Access-token expiry (epoch ms). */
  expiresAt?: number;
  /** True for the local demo session — nothing was verified by a server. */
  isDemo: boolean;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
}
