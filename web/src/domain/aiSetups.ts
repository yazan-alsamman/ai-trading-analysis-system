/**
 * AI setups (docs/ai-contract.md, docs/notifications.md#ai-setup-alerts-b11).
 *
 * ai-service proposes trade setups (entry, stop, target) per instrument and
 * profile; the backend evaluates on a schedule, stores them and tells the
 * users who follow an instrument and profile when a setup becomes ARMED.
 * Version 1 runs the setup RULES ONLY: no trained model, so `probability`,
 * `evR` and `grade` are null until a model passes its gate. The UI never fills
 * them in. Nothing here places a trade: "taken" is the user's own record.
 */

export const SETUP_STATES = ['DEVELOPING', 'ARMED', 'ACTIVE', 'CLOSED', 'EXPIRED', 'INVALIDATED'] as const;
export type SetupState = (typeof SETUP_STATES)[number];

export const SETUP_STATE_LABELS: Record<SetupState, string> = {
  DEVELOPING: 'Developing',
  ARMED: 'Armed: entry valid',
  ACTIVE: 'Active: entry reached',
  CLOSED: 'Closed',
  EXPIRED: 'Expired',
  INVALIDATED: 'Invalidated',
};

/** Profiles the backend accepts for follows (it answers 422 for any other). */
export const AI_PROFILES = ['intraday'] as const;
export type AIProfile = string;

export const AI_GRADES = ['A', 'B', 'C', 'D'] as const;
export type AIGrade = (typeof AI_GRADES)[number];

export interface AISetupInstrument {
  id: string;
  symbol: string;
  pricePrecision: number | null;
}

/** One setup as last reported (a notification of the user's inbox, or a live frame). */
export interface AISetup {
  setupId: string;
  state: SetupState;
  direction: 'buy' | 'sell';
  instrument: AISetupInstrument | null;
  profile: string | null;
  entry: number | null;
  sl: number | null;
  tp: number | null;
  rMultiple: number | null;
  /** Null without a model (v1). */
  probability: number | null;
  /** Null without a model (v1). */
  evR: number | null;
  /** Null in v1. */
  grade: AIGrade | null;
  validUntil: number | null;
  /** Why the last state change happened (the backend's text). */
  reason: string | null;
  realizedR: number | null;
  /** When the last state change happened. */
  updatedAt: number;
  /** The alert was sent late (outcomes are always sent). */
  late: boolean;
}

export interface AISizeInputs {
  balance: number;
  currency: string;
  leverage: number;
  riskPerTradePct: number;
  dailyLossLimitPct: number;
  maxDrawdownPct: number;
  /** Per field: `profile`, `config` or `default`. */
  sources: Record<string, string>;
}

/** The setup sized for the user's account (GET /ai/setups/{id}/size). */
export interface AISetupSize {
  setupId: string;
  lots: number;
  /** Money at risk at the stop, in the account currency. */
  riskAmount: number;
  marginRequired: number | null;
  feasible: boolean;
  warnings: string[];
  /** `remote` (ai-service) or `local` (the backend's sizing). */
  source: string;
  computedAt: number;
  inputs: AISizeInputs;
  taken: boolean;
}

export interface AIExplanation {
  setupId: string;
  lang: 'ar' | 'en';
  /** Null unless verified against the setup's numbers (or the fixed template). */
  text: string | null;
  status: string;
}

/** The user's record that they took a setup. */
export interface AITake {
  setupId: string;
  takenAt: number;
  lots: number | null;
  riskAmount: number | null;
  entryPrice: number | null;
  closedAt: number | null;
  realizedR: number | null;
  pnl: number | null;
  closeReason: string | null;
}

export interface AITrade extends AITake {
  instrumentId: string;
  profile: string;
  direction: string;
  state: SetupState;
  entry: number | null;
  sl: number | null;
  tp: number | null;
}

export interface AIFollow {
  instrumentId: string;
  profile: string;
  /** Only setups of this grade or better; null: all. */
  minGrade: AIGrade | null;
  createdAt: number;
}

/** A state change pushed on `ai:setups:{instrument_id}`. */
export interface AISetupEvent {
  instrumentId: string;
  setup: AISetup;
}

export function isOpenSetup(s: Pick<AISetup, 'state'>): boolean {
  return s.state === 'ARMED' || s.state === 'ACTIVE' || s.state === 'DEVELOPING';
}
