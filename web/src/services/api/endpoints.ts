/**
 * REST endpoints, relative to VITE_API_BASE_URL (default …/api/v1).
 *
 * `auth` matches the FastAPI backend in this monorepo (backend/app/api/v1).
 * Everything else is still a PROPOSAL, not yet implemented by the backend.
 * Paths are kept in this single file so aligning them is a one-file change.
 * Status of each endpoint is tracked in docs/API_INTEGRATION.md.
 */
export const endpoints = {
  auth: {
    login: '/auth/login', // implemented (backend Y02)
    register: '/auth/register', // implemented
    refresh: '/auth/refresh', // implemented, not yet used by the client
    logout: '/auth/logout', // implemented — body { refresh_token }
    me: '/users/me', // implemented
  },
  market: {
    candles: '/market/candles', // ?symbol=EURUSD&timeframe=15m&limit=500
    quotes: '/market/quotes',
  },
  opportunities: {
    list: '/opportunities', // ?symbol=&timeframe=
    latest: '/opportunities/latest', // ?symbol=&timeframe=
  },
  predictions: {
    history: '/predictions/history',
  },
  alerts: {
    list: '/alerts/price',
    item: (id: string) => `/alerts/price/${encodeURIComponent(id)}`,
    opportunityPreferences: '/alerts/opportunity-preferences',
  },
  assistant: {
    reply: '/assistant/replies', // POST { messages, context } — provider called server-side
  },
  community: {
    news: '/news',
    newsComments: (id: string) => `/news/${encodeURIComponent(id)}/comments`,
    posts: '/posts',
    experts: '/experts',
    conversation: (expertId: string) => `/experts/${encodeURIComponent(expertId)}/messages`,
  },
} as const;
