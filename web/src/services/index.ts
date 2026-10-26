import { createApiServices } from './api';
import type { SessionStore } from './api/session';
import type { AppConfig } from './config';
import { createDemoServices } from './demo';
import type { Services } from './types';

/**
 * Factory (Strategy pattern): the rest of the app receives a `Services`
 * object and never knows whether data is simulated or from the backend.
 */
export function createServices(cfg: AppConfig, store: SessionStore, onUnauthorized: () => void): Services {
  return cfg.dataSource === 'api' ? createApiServices(cfg, store, onUnauthorized) : createDemoServices(() => store.get());
}

export type { Services } from './types';
