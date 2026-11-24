import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import '@fontsource/instrument-serif/latin-400.css';
import '@fontsource/instrument-serif/latin-400-italic.css';
import './styles/index.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { AppProviders } from './app/AppProviders';
import { router } from './app/router';
import { ConfigErrorScreen } from './layouts/ConfigErrorScreen';
import { config } from './services/config';

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found');

createRoot(root).render(
  <StrictMode>
    {config.issues.length > 0 ? (
      <ConfigErrorScreen issues={config.issues} />
    ) : (
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    )}
  </StrictMode>,
);
