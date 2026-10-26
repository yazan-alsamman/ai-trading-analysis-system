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
    open: '/conversations', // POST { expert_id } → ConversationRead (201 new / 200 existing) · GET list
    messages: (conversationId: string) => `/conversations/${id(conversationId)}/messages`,
    read: (conversationId: string) => `/conversations/${id(conversationId)}/read`,
  },

  /* ---- full integration: every capability below has a web screen ---- */
  instruments: {
    item: (instrumentId: string) => `/market/instruments/${id(instrumentId)}`,
  },
  strategies: {
    catalog: '/strategies', // [StrategyDefinition]
    preview: (key: string) => `/strategies/${id(key)}/preview`, // POST → signals, markers, indicator lines
    mine: '/me/strategies', // GET [UserStrategyRead] · POST activate
    mineItem: (activationId: string) => `/me/strategies/${id(activationId)}`, // PATCH / DELETE
    signalPlans: '/me/signal-plans', // Page<SignalPlanRead>
  },
  customStrategies: {
    mine: '/me/custom-strategies', // GET Page<Summary> · POST create
    item: (strategyId: string) => `/me/custom-strategies/${id(strategyId)}`, // GET / PUT {version} / PATCH / DELETE
    clone: (strategyId: string) => `/me/custom-strategies/${id(strategyId)}/clone`,
    schema: '/custom-strategies/schema',
    validate: '/custom-strategies/validate', // always 200 {valid, errors, history}
    public: '/custom-strategies/public',
    clonePublic: (strategyId: string) => `/custom-strategies/public/${id(strategyId)}/clone`,
  },
  backtests: {
    list: '/backtests', // GET Page<Summary> · POST → 202 {id, status}
    item: (backtestId: string) => `/backtests/${id(backtestId)}`, // GET result · DELETE cancel/delete
    trades: (backtestId: string) => `/backtests/${id(backtestId)}/trades`,
    tradesCsv: (backtestId: string) => `/backtests/${id(backtestId)}/trades.csv`,
    compare: '/backtests/compare',
  },
  workspaces: {
    list: '/me/workspaces', // GET summaries · POST create
    item: (workspaceId: string) => `/me/workspaces/${id(workspaceId)}`, // GET / PUT {state, version} / PATCH / DELETE
    duplicate: (workspaceId: string) => `/me/workspaces/${id(workspaceId)}/duplicate`,
  },
  notificationSettings: {
    preferences: '/me/notification-preferences', // GET / PUT
    channels: '/me/notifications/channels',
    test: '/me/notifications/test',
    telegramLink: '/me/notifications/telegram/link', // POST → one-time code
    telegram: '/me/notifications/telegram', // DELETE unlink
    unreadCount: '/me/notifications/unread-count',
    item: (nid: string) => `/me/notifications/${id(nid)}`, // DELETE
  },
  alertHistory: '/me/price-alerts/history',
  social: {
    post: (postId: string) => `/posts/${id(postId)}`, // PATCH / DELETE
    like: (postId: string) => `/posts/${id(postId)}/like`, // POST / DELETE (idempotent)
    comment: (commentId: string) => `/comments/${id(commentId)}`, // PATCH / DELETE
    reports: '/reports',
    profile: (userId: string) => `/users/${id(userId)}/profile`,
    follow: (userId: string) => `/users/${id(userId)}/follow`, // POST / DELETE (idempotent)
    following: '/me/following',
    followers: '/me/followers',
  },
  expertsExtra: {
    item: (expertId: string) => `/experts/${id(expertId)}`,
    signals: (expertId: string) => `/experts/${id(expertId)}/signals`,
    checkout: '/subscriptions/checkout', // DEMO payments only
    subscriptions: '/me/subscriptions',
    cancel: (subId: string) => `/me/subscriptions/${id(subId)}/cancel`,
    resume: (subId: string) => `/me/subscriptions/${id(subId)}/resume`,
  },
  expertStudio: {
    profile: '/me/expert-profile', // GET (404 until created) / PUT
    plans: '/me/plans', // GET / POST
    plan: (planId: string) => `/me/plans/${id(planId)}`, // PATCH / DELETE (deactivates)
    earnings: '/me/earnings',
  },
  apiKeys: {
    list: '/me/api-keys', // GET / POST (the key is in the POST response only)
    scopes: '/me/api-keys/scopes',
    item: (keyId: string) => `/me/api-keys/${id(keyId)}`, // PATCH / DELETE (revoke)
    usage: (keyId: string) => `/me/api-keys/${id(keyId)}/usage`,
  },
} as const;
