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
  workspaceSharing: {
    order: '/me/workspaces/order', // PUT {ids: every id, in tab order}
    share: (workspaceId: string) => `/me/workspaces/${id(workspaceId)}/share`, // POST / DELETE (analysts, experts, admins)
    shared: (slug: string) => `/workspaces/shared/${id(slug)}`, // GET read-only copy
    importShared: (slug: string) => `/workspaces/shared/${id(slug)}/import`, // POST {name?}
  },
  chatExtra: {
    conversation: (conversationId: string) => `/conversations/${id(conversationId)}`,
    block: (conversationId: string) => `/conversations/${id(conversationId)}/block`,
    unblock: (conversationId: string) => `/conversations/${id(conversationId)}/unblock`,
    message: (messageId: string) => `/messages/${id(messageId)}`, // PATCH {body} (sender, 15 min) / DELETE (tombstone)
  },
  newsExtra: {
    article: (articleId: string) => `/news/${id(articleId)}`,
    sentiment: '/news/sentiment', // ?window=1h|24h|7d&instrument_id
    sources: '/news/sources',
  },
  indicators: {
    catalog: '/indicators',
    compute: (instrumentId: string) => `/market/instruments/${id(instrumentId)}/indicators`, // POST
  },
  riskSchema: '/risk/schema',
  health: {
    ready: '/health/ready',
    data: '/health/data', // 503 (with the report) when an instrument is degraded or has no data
  },
  devices: {
    list: '/me/devices', // GET; POST registers an FCM token (mobile app)
    item: (deviceId: string) => `/me/devices/${id(deviceId)}`, // DELETE
  },
  ingest: {
    news: '/ingest/news', // POST {articles} (admin login or a news:write key)
    sentiment: '/ingest/news/sentiment', // POST {items}
  },
  admin: {
    systemStatus: '/admin/system/status',
    realtimeStats: '/admin/realtime/stats',
    rateLimitStats: '/admin/rate-limits/stats',
    notificationStats: '/admin/notifications/stats',
    broadcast: '/admin/notifications/broadcast',
    paymentStats: '/admin/payments/stats',
    users: '/admin/users',
    userRole: (userId: string) => `/admin/users/${id(userId)}/role`,
    userStatus: (userId: string) => `/admin/users/${id(userId)}/status`,
    reports: '/admin/reports',
    resolveReport: (reportId: string) => `/admin/reports/${id(reportId)}/resolve`,
    conversations: '/admin/conversations',
    subscriptions: '/admin/subscriptions',
    refund: (invoiceId: string) => `/admin/invoices/${id(invoiceId)}/refund`,
    fastForward: (subId: string) => `/admin/subscriptions/${id(subId)}/fast-forward`, // DEMO tools only
    apiKeys: '/admin/api-keys',
    apiKey: (keyId: string) => `/admin/api-keys/${id(keyId)}`,
    newsSource: (sourceId: string) => `/admin/news/sources/${id(sourceId)}`,
    calendarRefresh: '/admin/calendar/refresh',
    calendarImport: '/admin/calendar/import', // multipart `file`
    instruments: '/admin/instruments',
    instrument: (instrumentId: string) => `/admin/instruments/${id(instrumentId)}`,
    instrumentCandles: (instrumentId: string) => `/admin/instruments/${id(instrumentId)}/candles`,
    ctrader: '/admin/feeds/ctrader', // GET status · PATCH {account_id}
    ctraderConnect: '/admin/feeds/ctrader/connect',
    ctraderCode: '/admin/feeds/ctrader/code',
    ctraderBackfill: '/admin/feeds/ctrader/backfill',
    aiSetups: '/admin/ai/setups',
    aiSetup: (setupId: string) => `/admin/ai/setups/${id(setupId)}`,
    aiOutbox: '/admin/ai/outbox',
    aiOutboxRetry: (rowId: number) => `/admin/ai/outbox/${rowId}/retry`,
    aiModels: '/admin/ai/models',
    aiModelActivate: (modelId: string) => `/admin/ai/models/${id(modelId)}/activate`,
  },
  aiSetups: {
    follows: '/me/ai/follows', // GET [FollowRead]
    follow: (instrumentId: string, profile: string) => `/me/ai/follows/${id(instrumentId)}/${id(profile)}`, // PUT {min_grade?} / DELETE
    size: (setupId: string) => `/ai/setups/${id(setupId)}/size`, // GET: sized for the caller's account
    explanation: (setupId: string) => `/ai/setups/${id(setupId)}/explanation`, // GET ?lang=ar|en
    take: (setupId: string) => `/ai/setups/${id(setupId)}/take`, // POST {lots?, entry_price?} / DELETE
    trades: '/me/ai/trades', // Page<AITradeRead>
    // Setups the user was told about: GET /me/notifications?type=ai_setup (no other user-facing list exists).
  },
  calendar: {
    events: '/calendar/events', // ?start&end (≤ 31 days)&currencies&min_impact&as_of
    history: (eventKey: string) => `/calendar/events/${id(eventKey)}/history`,
  },
  apiKeys: {
    list: '/me/api-keys', // GET / POST (the key is in the POST response only)
    scopes: '/me/api-keys/scopes',
    item: (keyId: string) => `/me/api-keys/${id(keyId)}`, // PATCH / DELETE (revoke)
    usage: (keyId: string) => `/me/api-keys/${id(keyId)}/usage`,
  },
} as const;
