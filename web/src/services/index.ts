import type { Session } from '@/domain/user';
import { createApiServices } from './api';
import type { AppConfig } from './config';
import { createDemoServices } from './demo';
import type { Services } from './types';

/**
 * Factory (Strategy pattern): the rest of the app receives a `Services`
 * object and never knows whether data is simulated or from the backend.
 */
export function createServices(cfg: AppConfig, getSession: () => Session | null, onUnauthorized: () => void): Services {
  return cfg.dataSource === 'api' ? createApiServices(cfg, getSession, onUnauthorized) : createDemoServices(getSession);
}

export type { Services } from './types';
