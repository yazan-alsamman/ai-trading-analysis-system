/**
 * PROPOSED REST endpoints — NOT confirmed by the backend team.
 *
 * Paths are kept in this single file so that aligning with the real Laravel
 * routes (or the team's Postman collection) is a one-file change.
 * Status of each endpoint is tracked in docs/API_INTEGRATION.md.
 */
export const endpoints = {
  auth: {
    login: '/auth/login',
    register: '/auth/register',
    logout: '/auth/logout',
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
  community: {
    news: '/news',
    newsComments: (id: string) => `/news/${encodeURIComponent(id)}/comments`,
    posts: '/posts',
    experts: '/experts',
    conversation: (expertId: string) => `/experts/${encodeURIComponent(expertId)}/messages`,
  },
} as const;
