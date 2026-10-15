import { createContext, useContext } from 'react';
import type { ChannelSettings, Density, Preferences, ThemePreference, TimeZonePreference, Workspace } from '@/domain/preferences';
import type { LoginInput, RegisterInput, Session } from '@/domain/user';
import type { Services } from '@/services/types';

function useRequired<T>(context: React.Context<T | null>, name: string): T {
  const value = useContext(context);
  if (value === null) throw new Error(`${name} must be used inside <AppProviders>`);
  return value;
}

/* ----------------------------------------------------------- services */
export const ServicesContext = createContext<Services | null>(null);
export const useServices = () => useRequired(ServicesContext, 'useServices');

/* -------------------------------------------------------- preferences */
export interface PreferencesApi {
  prefs: Preferences;
  /** The theme actually applied (system preference resolved). */
  resolvedTheme: 'dark' | 'light';
  /** IANA zone id for formatting. */
  timeZone: string;
  activeWorkspace: Workspace;
  setTheme(theme: ThemePreference): void;
  setDensity(density: Density): void;
  setTimeZone(tz: TimeZonePreference): void;
  setChannels(channels: ChannelSettings): void;
  updateWorkspace(patch: Partial<Omit<Workspace, 'id'>>, id?: string): void;
  createWorkspace(name: string): Workspace;
  deleteWorkspace(id: string): void;
  setActiveWorkspace(id: string): void;
}
export const PreferencesContext = createContext<PreferencesApi | null>(null);
export const usePreferences = () => useRequired(PreferencesContext, 'usePreferences');

/* --------------------------------------------------------------- auth */
export interface AuthApi {
  session: Session | null;
  login(input: LoginInput): Promise<void>;
  register(input: RegisterInput): Promise<void>;
  logout(): Promise<void>;
}
export const AuthContext = createContext<AuthApi | null>(null);
export const useAuth = () => useRequired(AuthContext, 'useAuth');

/* ------------------------------------------------------------- toasts */
export type ToastTone = 'info' | 'success' | 'warning' | 'danger';
export interface ToastApi {
  notify(message: string, tone?: ToastTone): void;
}
export const ToastContext = createContext<ToastApi | null>(null);
export const useToast = () => useRequired(ToastContext, 'useToast');
