import { EMPTY_CONTEXT, type AssistantContext } from '@/domain/assistant';
import { composeReply, DEMO_ASSISTANT } from '@/services/demo/assistant';
import type { AssistantService } from '@/services/types';
import { buildShowcase, SHOWCASE_PROFILE, SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME } from '../showcase';

/**
 * The public website's assistant: the SAME rule-based demo composer the app
 * uses (services/demo/assistant.ts), answering about the website's simulated
 * showcase setup. Its clock is fixed at the showcase time so that answers
 * about that example stay coherent (the setup is not "expired" for visitors).
 *
 * It is not a language model and never calls a server; the UI says so.
 */
export function createShowcaseAssistant(latencyMs = 380): AssistantService {
  return {
    describe: () => DEMO_ASSISTANT,
    async reply(messages, context, options) {
      await new Promise<void>((resolve, reject) => {
        const signal = options?.signal;
        if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
        const t = window.setTimeout(resolve, latencyMs);
        signal?.addEventListener('abort', () => {
          window.clearTimeout(t);
          reject(new DOMException('Aborted', 'AbortError'));
        });
      });
      const question = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
      return composeReply(question, context, buildShowcase().opportunity.generatedAt);
    },
  };
}

/** What the public assistant can see: the simulated showcase setup, plus the example account when shared. */
export function showcaseContext(shareExampleAccount: boolean): AssistantContext {
  const s = buildShowcase();
  return {
    ...EMPTY_CONTEXT,
    symbol: SHOWCASE_SYMBOL,
    timeframe: SHOWCASE_TIMEFRAME,
    lastPrice: s.candles[s.candles.length - 1]?.close ?? null,
    priceProvenance: 'demo',
    feedStatus: 'demo',
    opportunity: s.opportunity,
    confluence: [s.opportunity],
    riskProfile: shareExampleAccount ? SHOWCASE_PROFILE : null,
  };
}

export const PUBLIC_THREAD_KEY = 'ata.assistant.public.v1';
