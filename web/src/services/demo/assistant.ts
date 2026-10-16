import type { AssistantContext, AssistantDescription, AssistantReply } from '@/domain/assistant';
import { describeContext } from '@/domain/assistant';
import { getInstrument } from '@/domain/instruments';
import { timeframeSeconds } from '@/domain/market';
import { RISK_LABELS, SETUP_LABELS, type Opportunity } from '@/domain/opportunity';
import { invalidationNotes, missingNotes } from '@/domain/research';
import { computeTradeRisk, evaluateLimits, planFromOpportunity } from '@/domain/risk';
import { localId } from '@/lib/cn';
import { formatMoney, formatPct, formatPercent, formatPrice, formatProbabilityBand, formatR, formatRiskReward, formatUnits } from '@/lib/format';

/**
 * Demo assistant: a deterministic, rule-based EVIDENCE COMPOSER.
 *
 * It is deliberately not presented as AI. Every sentence is derived from the
 * fields in `AssistantContext`; when a field is missing it says so instead of
 * filling the gap. A real model replaces this through the API implementation
 * (`services/api`), with provider keys held by the backend.
 */

export const DEMO_ASSISTANT: AssistantDescription = {
  provider: 'demo-rules',
  label: 'Rule-based demo',
  description:
    'Not a language model. It assembles answers only from the data listed under “Context” using fixed rules, so it cannot reason beyond that data.',
};

export type Intent = 'explain' | 'invalidate' | 'risk' | 'compare' | 'evidence' | 'missing' | 'glossary' | 'unknown';

const GLOSSARY: { keys: RegExp; term: string; text: string }[] = [
  {
    keys: /reward.?to.?risk|risk.?reward|r\s*:\s*r|\brr\b/i,
    term: 'Reward : risk',
    text: 'How far the target is from the entry compared with how far the stop is. **1 : 2** means the planned gain is twice the planned loss. It says nothing about how *likely* either outcome is — that is what the probability is for.',
  },
  {
    keys: /expected value|\bev\b/i,
    term: 'Expected value (R)',
    text: 'The average result per trade, measured in units of the amount risked (R), *if* the probability were exactly right: **probability × reward − (1 − probability) × 1**. +0.3R means an average gain of 30 % of the risk per trade over many trades. A single trade still either wins or loses.',
  },
  {
    keys: /probabilit/i,
    term: 'Probability',
    text: 'In this platform the model’s probability is the estimated chance that the **take-profit is reached before the stop-loss** within the horizon. It is an estimate, not a guarantee, and its reliability is measured on the Insights page (calibration, Brier score).',
  },
  {
    keys: /calibrat/i,
    term: 'Calibration',
    text: 'A model is well calibrated when its 70 % calls come true about 70 % of the time. The Insights page groups past predictions by stated probability and compares them with the observed hit rate.',
  },
  {
    keys: /brier/i,
    term: 'Brier score',
    text: 'The mean squared difference between the predicted probability and the outcome (1 = target hit, 0 = stop hit). **Lower is better**; always answering 50 % scores 0.25.',
  },
  {
    keys: /\bema\b|moving average/i,
    term: 'EMA (exponential moving average)',
    text: 'An average of recent closing prices that gives more weight to the newest candles. Price above a rising EMA is commonly read as an up-trend; it lags price by design.',
  },
  {
    keys: /\brsi\b|relative strength/i,
    term: 'RSI (relative strength index)',
    text: 'A 0–100 oscillator comparing the size of recent gains with recent losses. Readings above 70 are conventionally called overbought and below 30 oversold; in strong trends it can stay there for a long time.',
  },
  {
    keys: /\batr\b|average true range|volatility/i,
    term: 'ATR (average true range)',
    text: 'The average size of recent candles, including gaps. It is a volatility measure: a wider ATR means stops need more room for the same chance of not being hit by noise.',
  },
  {
    keys: /stop.?loss/i,
    term: 'Stop-loss',
    text: 'The price at which a trade is closed to cap the loss. In the Risk module the distance from entry to stop, and your capital and risk %, determine the position size.',
  },
];

export function detectIntent(question: string): Intent {
  const q = question.toLowerCase();
  if (/(missing|before i can|what (else )?do (i|you) need|unknown|gaps?\b)/.test(q)) return 'missing';
  if (/(invalidat|wrong|fail|what could go|break|cancel)/.test(q)) return 'invalidate';
  if (/(risk for|position size|size (the|this|my)|lot|how much (can|should) i|capital|calculate)/.test(q)) return 'risk';
  if (/(compare|timeframe|alignment|align|agree|15m|4h)/.test(q)) return 'compare';
  if (/(evidence|why|factor|support|reason)/.test(q)) return 'evidence';
  if (/(in simple terms|what is|what's|what does .* mean|define|meaning of|explain (the )?(rsi|ema|atr|brier|calibration|reward|expected|probability))/.test(q) && GLOSSARY.some((g) => g.keys.test(q)))
    return 'glossary';
  if (/(explain|summar|analysis|what does the model|current|overview|read)/.test(q)) return 'explain';
  if (GLOSSARY.some((g) => g.keys.test(q))) return 'glossary';
  return 'unknown';
}

const dirWord = (o: Opportunity) => (o.direction === 'long' ? 'long (buy-side)' : o.direction === 'short' ? 'short (sell-side)' : 'neutral');
const label = (o: Opportunity) => `${getInstrument(o.symbol).display} ${o.timeframe}`;
const demoNote = (o: Opportunity | null) =>
  o?.provenance === 'demo' ? '\n\n> Simulated data: this model output was generated in the browser by a demo heuristic, not by the project’s trained model.' : '';

function noAnalysis(ctx: AssistantContext): string {
  const where = ctx.symbol && ctx.timeframe ? ` for ${getInstrument(ctx.symbol).display} ${ctx.timeframe}` : '';
  return `I have no model output${where} in my context, so I cannot describe one. Open the Workspace on an instrument (or wait for its analysis to load) and ask again.`;
}

function explain(ctx: AssistantContext): string {
  const o = ctx.opportunity;
  if (!o) return noAnalysis(ctx);
  const inst = getInstrument(o.symbol);
  if (o.status !== 'detected') {
    return `**${label(o)}: no opportunity.** The model evaluated the latest candles and its output did not meet the detection threshold, so it suggests no entry, stop-loss or target.${demoNote(o)}`;
  }
  const p = inst.pricePrecision;
  const hours = (o.horizonCandles * timeframeSeconds(o.timeframe)) / 3600;
  const lines = [
    `**${label(o)} — ${dirWord(o)} setup detected.**`,
    '',
    `The model estimates a **${formatPercent(o.probability)}** probability that the take-profit is reached before the stop-loss within ${o.horizonCandles} candles (≈ ${hours < 48 ? `${hours} h` : `${Math.round(hours / 24)} d`}).${o.confidenceBand ? ` Its confidence band is ${formatProbabilityBand(o.confidenceBand)}.` : ' It did not supply a confidence band.'}`,
    '',
    '| Item | Model output |',
    '| --- | --- |',
    `| Entry zone | ${formatPrice(o.entryZone.low, p)} – ${formatPrice(o.entryZone.high, p)} |`,
    `| Stop-loss zone | ${formatPrice(o.stopLossZone.low, p)} – ${formatPrice(o.stopLossZone.high, p)} |`,
    `| Take-profit zone | ${formatPrice(o.takeProfitZone.low, p)} – ${formatPrice(o.takeProfitZone.high, p)} |`,
    `| Reward : risk | ${formatRiskReward(o.riskReward)} |`,
    `| Expected value | ${formatR(o.expectedValueR)} |`,
    `| Setup · risk level | ${SETUP_LABELS[o.setupType]} · ${RISK_LABELS[o.riskLevel]} |`,
    '',
  ];
  const top = [...o.factors].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 2);
  if (top.length) lines.push(`Strongest contributing factors: ${top.map((f) => `*${f.label}*`).join(' and ')}. Ask “summarise the evidence” for all of them.`, '');
  if (ctx.lastPrice !== null) lines.push(`Last price in context: ${formatPrice(ctx.lastPrice, p)}${ctx.priceProvenance === 'demo' ? ' (simulated)' : ''}.`, '');
  lines.push('This is a probabilistic estimate, not a prediction that will come true and not financial advice.');
  return lines.join('\n') + demoNote(o);
}

function invalidate(ctx: AssistantContext, nowMs: number): string {
  const o = ctx.opportunity;
  if (!o) return noAnalysis(ctx);
  if (o.status !== 'detected') return `There is no active setup on ${label(o)} to invalidate — the model reported no opportunity.${demoNote(o)}`;
  const p = getInstrument(o.symbol).pricePrecision;
  const notes = invalidationNotes(o, ctx.confluence, nowMs, (v) => formatPrice(v, p));
  return (
    [`What would invalidate the ${label(o)} ${o.direction} analysis:`, '', ...notes.map((n) => `- **${n.title}.** ${n.detail}`), '', 'I can only list conditions derived from the data in context; news events and liquidity are not in my context.'].join('\n') +
    demoNote(o)
  );
}

function risk(ctx: AssistantContext): string {
  const o = ctx.opportunity;
  if (!ctx.riskProfile) return 'Your risk profile is not shared with me. Turn on “Share my risk profile” under Context, or use the Capital & risk page directly.';
  if (!o || o.status !== 'detected') return `${noAnalysis(ctx)}\n\nYou can still size any trade manually on the Capital & risk page.`;
  const plan = planFromOpportunity(o);
  if (!plan) return 'This model output has no directional plan to size.';
  const inst = getInstrument(o.symbol);
  const rp = ctx.riskProfile;
  const res = computeTradeRisk(rp, { instrument: inst, ...plan, riskPct: rp.maxRiskPerTradePct, quoteToAccountRate: null });
  if (res.kind !== 'ok') {
    return ['I cannot size this trade yet:', '', ...res.issues.map((i) => `- ${i.message}`), '', 'Complete these on the Capital & risk page; I will not estimate missing values.'].join('\n');
  }
  const r = res.risk;
  const cur = rp.currency;
  const p = inst.pricePrecision;
  const lines = [
    `Sizing the ${label(o)} plan at your **${formatPct(rp.maxRiskPerTradePct)}** risk per trade (midpoints of the model’s zones):`,
    '',
    '| | Value |',
    '| --- | --- |',
    `| Entry · stop · target | ${formatPrice(plan.entry, p)} · ${formatPrice(plan.stop, p)} · ${formatPrice(plan.target, p)} |`,
    `| Position size | ${formatUnits(r.units, inst.base)}${r.lots ? ` (${r.lots.rounded ?? r.lots.exact.toFixed(4)} lots)` : ''} |`,
    `| Money at risk (stop hit) | ${formatMoney(r.monetaryRisk, cur)} · ${formatPct(r.riskPctOfCapital)} of capital |`,
    `| Potential reward (target hit) | ${formatMoney(r.potentialReward, cur)} |`,
    `| Reward : risk | ${formatRiskReward(r.riskReward)} |`,
    '',
  ];
  const breaches = evaluateLimits(rp, r.monetaryRisk).filter((l) => l.status === 'breach');
  lines.push(breaches.length ? `**Limit check:** this would breach ${breaches.map((b) => b.label.toLowerCase()).join(' and ')}.` : '**Limit check:** within all of your configured limits.');
  lines.push('', ...res.notes.map((n) => `- ${n}`), '', 'Your capital, limits and current exposure are values you entered; I have not verified them.');
  return lines.join('\n') + demoNote(o);
}

function compare(ctx: AssistantContext): string {
  const items = [...ctx.confluence].sort((a, b) => timeframeSeconds(a.timeframe) - timeframeSeconds(b.timeframe));
  if (items.length === 0) return 'I have no multi-timeframe analyses in context. Open the Workspace on an instrument and ask again.';
  const roles: Record<string, string> = { '15m': 'Detection', '1h': 'Confirmation', '4h': 'Regime' };
  const rows = items.map((o) =>
    o.status === 'detected'
      ? `| ${o.timeframe} · ${roles[o.timeframe] ?? ''} | ${o.direction} | ${formatPercent(o.probability)} | ${formatRiskReward(o.riskReward)} |`
      : `| ${o.timeframe} · ${roles[o.timeframe] ?? ''} | none | — | — |`,
  );
  const dirs = new Set(items.filter((o) => o.status === 'detected').map((o) => o.direction));
  const verdict =
    dirs.size === 0
      ? 'No timeframe currently shows a setup.'
      : dirs.size === 1 && items.every((o) => o.status === 'detected')
        ? `All timeframes agree: **${[...dirs][0]}**. Agreement is supportive but does not raise any single probability.`
        : 'The timeframes **do not fully agree**. Treat the lower-timeframe signal with more caution when the higher timeframe disagrees.';
  const first = items[0];
  return [`Timeframe comparison for ${first ? getInstrument(first.symbol).display : ''}:`, '', '| Timeframe | Direction | Probability | R : R |', '| --- | --- | --- | --- |', ...rows, '', verdict].join('\n') + demoNote(first ?? null);
}

function evidence(ctx: AssistantContext): string {
  const o = ctx.opportunity;
  if (!o) return noAnalysis(ctx);
  if (o.factors.length === 0) return `The model output for ${label(o)} carries no factor explanations.${demoNote(o)}`;
  const rows = [...o.factors]
    .sort((a, b) => b.contribution - a.contribution)
    .map((f) => `| ${f.label} | ${f.contribution >= 0 ? 'Supports' : 'Opposes'} | ${f.contribution >= 0 ? '+' : '−'}${Math.abs(f.contribution).toFixed(2)} | ${f.detail} |`);
  return (
    [
      `Evidence attached to the ${label(o)} output (${o.status === 'detected' ? o.direction : 'no opportunity'}):`,
      '',
      '| Factor | Effect | Weight | Detail |',
      '| --- | --- | --- | --- |',
      ...rows,
      '',
      'Weights are the model’s attribution of its own output to each factor; they explain the model, they do not prove the market will follow.',
    ].join('\n') + demoNote(o)
  );
}

function missing(ctx: AssistantContext, nowMs: number): string {
  const notes = missingNotes({
    opportunity: ctx.opportunity,
    priceProvenance: ctx.priceProvenance,
    feedStatus: ctx.feedStatus,
    confluenceCount: ctx.confluence.length,
    riskProfile: ctx.riskProfile,
    symbol: ctx.symbol,
    nowMs,
  });
  return ['Before relying on this analysis, these items are missing or unverified:', '', ...notes.map((n) => `- **${n.title}.** ${n.detail}`)].join('\n');
}

function glossary(question: string): string {
  const hits = GLOSSARY.filter((g) => g.keys.test(question));
  if (!hits.length) return unknown();
  return hits.map((g) => `**${g.term}.** ${g.text}`).join('\n\n');
}

function unknown(): string {
  return [
    'I am a rule-based demo, so I can only answer a fixed set of questions from the data in context:',
    '',
    '- Explain the current analysis',
    '- What would invalidate it',
    '- Calculate the risk for your capital and stop-loss',
    '- Compare the analysis across timeframes',
    '- Summarise the supporting evidence',
    '- What information is missing',
    '- Define a term (reward : risk, expected value, probability, calibration, Brier score, EMA, RSI, ATR, stop-loss)',
  ].join('\n');
}

/** Pure composer — exported for tests. */
export function composeReply(question: string, ctx: AssistantContext, nowMs: number): AssistantReply {
  const intent = detectIntent(question);
  const content =
    intent === 'explain'
      ? explain(ctx)
      : intent === 'invalidate'
        ? invalidate(ctx, nowMs)
        : intent === 'risk'
          ? risk(ctx)
          : intent === 'compare'
            ? compare(ctx)
            : intent === 'evidence'
              ? evidence(ctx)
              : intent === 'missing'
                ? missing(ctx, nowMs)
                : intent === 'glossary'
                  ? glossary(question)
                  : unknown();
  const used = intent === 'glossary' || intent === 'unknown' ? [] : describeContext(ctx);
  return { id: localId('reply'), content, createdAt: nowMs, provider: 'demo-rules', contextUsed: used };
}
