import type { InstrumentSymbol } from './instruments';
import type { Timeframe } from './market';

/** SF7 — delivery channels. */
export type NotificationChannel = 'app' | 'email' | 'telegram';

export const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  app: 'In-app',
  email: 'Email',
  telegram: 'Telegram',
};

/** SF16 — notify when a pair reaches a user-specified level. */
export type AlertCondition = 'crosses_above' | 'crosses_below';

export const CONDITION_LABELS: Record<AlertCondition, string> = {
  crosses_above: 'Crosses above',
  crosses_below: 'Crosses below',
};

export type AlertStatus = 'active' | 'paused' | 'triggered';

export interface PriceAlert {
  id: string;
  symbol: InstrumentSymbol;
  condition: AlertCondition;
  price: number;
  channels: NotificationChannel[];
  note?: string;
  status: AlertStatus;
  createdAt: number;
  triggeredAt?: number;
}

export type PriceAlertDraft = Pick<PriceAlert, 'symbol' | 'condition' | 'price' | 'channels' | 'note'>;

/**
 * SF2 — notifications for high-probability opportunities.
 * Deliberately NOT called "guaranteed": the model reports probabilities only.
 */
export interface OpportunityAlertPreferences {
  enabled: boolean;
  /** Notify only at or above this probability (0–1). */
  minProbability: number;
  symbols: InstrumentSymbol[];
  timeframes: Timeframe[];
  directions: ('long' | 'short')[];
  channels: NotificationChannel[];
}
