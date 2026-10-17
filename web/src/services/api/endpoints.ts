/**
 * REST endpoints of the FastAPI backend, relative to VITE_API_BASE_URL (…/api/v1).
 *
 * Every path below exists in the committed contract (docs/api/openapi.json,
 * validated in CI) and was checked against backend/app/api/v1. Capabilities
 * the backend does not offer are NOT listed here; their service methods
 * report `not_available` instead (docs/BACKEND_INTEGRATION_GAP_ANALYSIS.md).
 */
const id = (v: string) => encodeURIComponent(v);

export const endpoints = {
  auth: {
    login: '/auth/login', // → TokenPair
    register: '/auth/register', // → UserRead (no token)
    refresh: '/auth/refresh', // rotates the refresh token (reuse ⇒ all sessions revoked)
    logout: '/auth/logout', // 204, body { refresh_token }
  },
  users: {
    me: '/users/me', // GET UserRead · PATCH { full_name }
    password: '/users/me/password', // POST { current_password, new_password } → 204
  },
  market: {
    instruments: '/market/instruments', // Page<InstrumentRead>
    candles: (instrumentId: string) => `/market/instruments/${id(instrumentId)}/candles`, // ?timeframe=&limit=
  },
  signals: {
    list: '/signals', // strategy-engine signals, Page<SignalRead>
  },
  risk: {
    profile: '/me/risk-profile', // GET / PUT
    positionSize: '/risk/position-size', // POST → server plan
  },
  alerts: {
    list: '/me/price-alerts', // GET Page · POST create
    item: (alertId: string) => `/me/price-alerts/${id(alertId)}`, // PATCH / DELETE
  },
  notifications: {
    list: '/me/notifications',
    readAll: '/me/notifications/read-all',
    read: (nid: string) => `/me/notifications/${id(nid)}/read`,
  },
  news: {
    list: '/news', // Page<ArticleRead>
  },
  posts: {
    list: '/posts', // GET feed · POST create
    comments: (postId: string) => `/posts/${id(postId)}/comments`,
  },
  experts: {
    list: '/experts', // Page<ExpertCard>
  },
  chat: {
    open: '/conversations', // POST { expert_id } → ConversationRead (201 new / 200 existing)
    messages: (conversationId: string) => `/conversations/${id(conversationId)}/messages`,
  },
} as const;
