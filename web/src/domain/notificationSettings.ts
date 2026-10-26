/**
 * Server-side notification settings (docs/notifications.md): per-event,
 * per-channel preferences, quiet hours, hourly caps, language, and what each
 * delivery channel can do on this server. The in-app inbox always receives
 * every notification; the matrix controls the external channels only.
 */

export type ExternalChannel = 'telegram' | 'email' | 'push';
export const EXTERNAL_CHANNELS: readonly ExternalChannel[] = ['telegram', 'email', 'push'];

export const CHANNEL_LABELS: Record<ExternalChannel | 'in_app', string> = {
  in_app: 'In-app',
  telegram: 'Telegram',
  email: 'Email',
  push: 'Mobile push',
};

/** Event types that have a matrix entry (`post_liked` never leaves the app). */
export const NOTIFICATION_EVENTS: readonly { type: string; label: string }[] = [
  { type: 'signal', label: 'Strategy signals' },
  { type: 'price_alert', label: 'Price alerts' },
  { type: 'backtest_completed', label: 'Backtest completed' },
  { type: 'backtest_failed', label: 'Backtest failed' },
  { type: 'security', label: 'Security (new sign-in, password, API keys)' },
  { type: 'system', label: 'System messages' },
  { type: 'new_post', label: 'New post from someone you follow' },
  { type: 'comment_reply', label: 'Replies to your posts and comments' },
  { type: 'content_hidden', label: 'Moderation of your content' },
  { type: 'chat_message', label: 'Expert chat messages' },
  { type: 'subscription_started', label: 'Subscription started' },
  { type: 'subscription_renewed', label: 'Subscription renewed' },
  { type: 'subscription_payment_failed', label: 'Subscription payment failed' },
  { type: 'subscription_canceled', label: 'Subscription canceled' },
  { type: 'new_subscriber', label: 'New subscriber (experts)' },
];

export type ChannelMatrix = Record<string, Partial<Record<ExternalChannel, boolean>>>;

export interface NotificationPreferences {
  matrix: ChannelMatrix;
  /** 0–1: signals weaker than this are not sent externally. */
  minSignalStrength: number;
  /** Only send signals whose trade plan is valid. */
  onlyValidPlans: boolean;
  quietHours: { start: string; end: string; tz: string } | null;
  /** Language of notification texts. */
  language: 'ar' | 'en';
  maxPerHour: Partial<Record<ExternalChannel, number>>;
  updatedAt: number;
}

export interface ChannelInfo {
  /** False: the server has no configuration for this channel ("not available"). */
  enabledOnServer: boolean;
  linked: boolean | null;
  username: string | null;
  mode: string | null;
  address: string | null;
  devices: number | null;
}

export type ChannelStatus = Record<'in_app' | ExternalChannel, ChannelInfo>;

export interface TelegramLink {
  code: string;
  deepLink: string | null;
  botUsername: string | null;
  expiresInSeconds: number;
}

export interface TestDelivery {
  channel: string;
  target: string;
  /** e.g. `sent`, `queued`, `skipped`, `failed`. */
  status: string;
  lastError: string | null;
}

/** A price alert that fired (GET /me/price-alerts/history). */
export interface AlertTrigger {
  notificationId: string;
  alertId: string | null;
  symbol: string | null;
  condition: string | null;
  value: number | null;
  price: number | null;
  barTime: number | null;
  changePct: number | null;
  note: string | null;
  createdAt: number;
}
