import { getInstrument, type InstrumentSymbol } from './instruments';
import type { FeedStatus, Provenance, Timeframe } from './market';
import type { Opportunity } from './opportunity';
import type { RiskProfile } from './risk';

/**
 * AI assistant — provider-agnostic contract.
 *
 * The assistant may only claim access to what is in `AssistantContext`. The
 * client builds the context from data already on screen and shows the user
 * exactly which items are included. Provider credentials never reach the
 * browser: a real model is called by the backend (docs/API_INTEGRATION.md §7).
 */

export type AssistantRole = 'user' | 'assistant';

export interface AssistantMessage {
  id: string;
  role: AssistantRole;
  /** Markdown (assistant) or plain text (user). */
  content: string;
  createdAt: number;
  /** Assistant replies only: which context items the answer drew on. */
  contextUsed?: string[];
  /** Assistant replies only: what produced the answer. */
  provider?: AssistantProviderKind;
}

export type AssistantProviderKind = 'demo-rules' | 'remote';

export interface AssistantContext {
  symbol: InstrumentSymbol | null;
  timeframe: Timeframe | null;
  lastPrice: number | null;
  priceProvenance: Provenance | null;
  feedStatus: FeedStatus | null;
  /** Latest model output for symbol/timeframe, if loaded. */
  opportunity: Opportunity | null;
  /** Model outputs for the same symbol on other timeframes. */
  confluence: Opportunity[];
  /** Shared only when the user allows it. */
  riskProfile: RiskProfile | null;
}

export const EMPTY_CONTEXT: AssistantContext = {
  symbol: null,
  timeframe: null,
  lastPrice: null,
  priceProvenance: null,
  feedStatus: null,
  opportunity: null,
  confluence: [],
  riskProfile: null,
};

export interface AssistantReply {
  id: string;
  content: string;
  createdAt: number;
  provider: AssistantProviderKind;
  contextUsed: string[];
}

export interface AssistantDescription {
  provider: AssistantProviderKind;
  /** Short name for the UI, e.g. "Rule-based demo". */
  label: string;
  /** One sentence on what it is and is not. */
  description: string;
}

/** Human-readable list of what a context contains — shown as chips and sent nowhere else. */
export function describeContext(ctx: AssistantContext): string[] {
  const items: string[] = [];
  if (ctx.symbol && ctx.timeframe) items.push(`${getInstrument(ctx.symbol).display} ${ctx.timeframe}`);
  if (ctx.lastPrice !== null) items.push(ctx.priceProvenance === 'demo' ? 'Last price (simulated)' : 'Last price');
  if (ctx.opportunity) items.push(ctx.opportunity.provenance === 'demo' ? 'Model output (simulated)' : 'Model output');
  if (ctx.confluence.length > 0) items.push(`${ctx.confluence.length} timeframe analyses`);
  if (ctx.riskProfile) items.push('Your risk profile');
  return items;
}

/** Suggested prompts. Each maps to a capability the demo composer really has. */
export const SUGGESTED_PROMPTS = [
  'Explain the current analysis',
  'What would invalidate this projection?',
  'Calculate the risk for my capital and stop-loss',
  'Compare the analysis across timeframes',
  'Summarise the evidence behind this signal',
  'What information is missing before I can evaluate this?',
  'Explain reward-to-risk in simple terms',
] as const;
