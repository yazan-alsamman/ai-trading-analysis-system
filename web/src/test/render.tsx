import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router';
import { AppProviders } from '@/app/AppProviders';
import { createDemoServices } from '@/services/demo';
import type { Services } from '@/services/types';

/** Render inside the real providers with injectable services (demo by default). */
export function renderWithProviders(ui: ReactElement, { services, route = '/' }: { services?: Services; route?: string } = {}) {
  const svc = services ?? createDemoServices(() => null);
  return {
    services: svc,
    ...render(
      <AppProviders services={svc}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AppProviders>,
    ),
  };
}
