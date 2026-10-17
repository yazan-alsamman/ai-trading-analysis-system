import { describe, expect, it } from 'vitest';
import { parseMarkdown } from '@/components/ui/markdownParser';
import { EMPTY_CONTEXT, SUGGESTED_PROMPTS, type AssistantContext } from '@/domain/assistant';
import type { Opportunity } from '@/domain/opportunity';
import { DEFAULT_RISK_PROFILE } from '@/domain/risk';
import { composeReply, detectIntent } from './assistant';

const opp = (patch: Partial<Opportunity> = {}): Opportunity => ({
  id: 'o1',
  symbol: 'XAUUSD',
  timeframe: '1h',
  status: 'detected',
  direction: 'long',
  setupType: 'trend_following',
  riskLevel: 'medium',
  probability: 0.68,
  entryZone: { low: 2349, high: 2351 },
  stopLossZone: { low: 2339, high: 2341 },
  takeProfitZone: { low: 2369, high: 2371 },
  riskReward: 2,
  expectedValueR: 0.36,
  factors: [
    { id: 'f1', label: 'EMA 20 above EMA 50', detail: 'Trend structure intact', contribution: 0.32 },
    { id: 'f2', label: 'RSI near overbought', detail: 'Momentum stretched', contribution: -0.08 },
  ],
  horizonCandles: 20,
  signalCandleTime: 0,
  generatedAt: 1_000,
  validUntil: 10_000,
  modelVersion: 'test',
  provenance: 'demo',
  ...patch,
});

const ctx = (patch: Partial<AssistantContext> = {}): AssistantContext => ({
  ...EMPTY_CONTEXT,
  symbol: 'XAUUSD',
  timeframe: '1h',
  lastPrice: 2350.5,
  priceProvenance: 'demo',
  feedStatus: 'demo',
  opportunity: opp(),
  confluence: [opp({ timeframe: '15m' }), opp(), opp({ timeframe: '4h', direction: 'short' })],
  ...patch,
});

describe('demo assistant intent routing', () => {
  it('routes every suggested prompt to a real capability (never the fallback)', () => {
    for (const prompt of SUGGESTED_PROMPTS) expect(detectIntent(prompt), prompt).not.toBe('unknown');
    expect(detectIntent('Explain the current analysis')).toBe('explain');
    expect(detectIntent('What would invalidate this projection?')).toBe('invalidate');
    expect(detectIntent('Calculate the risk for my capital and stop-loss')).toBe('risk');
    expect(detectIntent('Compare the analysis across timeframes')).toBe('compare');
    expect(detectIntent('Summarise the evidence behind this signal')).toBe('evidence');
    expect(detectIntent('What information is missing before I can evaluate this?')).toBe('missing');
    expect(detectIntent('Explain reward-to-risk in simple terms')).toBe('glossary');
    expect(detectIntent('Will gold hit 3000 next year?')).toBe('unknown');
  });
});

describe('demo assistant replies', () => {
  it('explains only fields that are in the model output and labels simulated data', () => {
    const r = composeReply('Explain the current analysis', ctx(), 5_000);
    expect(r.provider).toBe('demo-rules');
    expect(r.content).toContain('**68%**');
    expect(r.content).toContain('It did not supply a confidence band.');
    expect(r.content).toContain('Simulated data');
    expect(r.contextUsed).toContain('Model output (simulated)');
  });

  it('says it has no analysis instead of inventing one', () => {
    const r = composeReply('Explain the current analysis', ctx({ opportunity: null }), 5_000);
    expect(r.content).toMatch(/I have no model output/);
  });

  it('lists invalidation conditions from the data, including timeframe disagreement and opposing factors', () => {
    const r = composeReply('What would invalidate this?', ctx(), 5_000);
    expect(r.content).toContain('Price trades below the stop-loss zone');
    expect(r.content).toContain('2,339.00');
    expect(r.content).toContain('4h reads short');
    expect(r.content).toContain('Other timeframes disagree');
    expect(r.content).toContain('RSI near overbought');
  });

  it('refuses to size without the shared risk profile, and names missing capital', () => {
    expect(composeReply('Calculate the risk for my capital', ctx(), 5_000).content).toMatch(/not shared/);
    const noCapital = composeReply('Calculate the risk for my capital', ctx({ riskProfile: DEFAULT_RISK_PROFILE }), 5_000);
    expect(noCapital.content).toContain('Enter your account capital.');
  });

  it('sizes the model plan with the same domain calculation as the Risk page', () => {
    const r = composeReply('Calculate the risk for my capital', ctx({ riskProfile: { ...DEFAULT_RISK_PROFILE, capital: 10_000 } }), 5_000);
    expect(r.content).toContain('10.00 oz'); // $100 / $10 stop distance
    expect(r.content).toContain('$100.00');
    expect(r.content).toContain('$200.00');
    expect(r.content).toContain('within all of your configured limits');
  });

  it('compares timeframes and reports disagreement', () => {
    const r = composeReply('Compare timeframes', ctx(), 5_000);
    expect(r.content).toContain('| 4h · Regime | short |');
    expect(r.content).toContain('do not fully agree');
  });

  it('lists missing information honestly', () => {
    const r = composeReply('What is missing before I can evaluate this?', ctx(), 5_000);
    expect(r.content).toContain('No confidence band');
    expect(r.content).toContain('Prices are simulated');
    expect(r.content).toContain('Your risk profile is not shared');
  });

  it('answers glossary questions without claiming any market context', () => {
    const r = composeReply('What is a Brier score?', ctx(), 5_000);
    expect(r.content).toContain('Lower is better');
    expect(r.contextUsed).toEqual([]);
  });
});

describe('markdown parser', () => {
  it('parses headings, lists, quotes and tables', () => {
    const blocks = parseMarkdown('# Title\n\nSome **bold** text\n\n- a\n- b\n\n> quoted\n\n| A | B |\n| --- | --- |\n| 1 | 2 |');
    expect(blocks.map((b) => b.kind)).toEqual(['heading', 'paragraph', 'list', 'quote', 'table']);
    const table = blocks[4];
    expect(table?.kind === 'table' && table.rows).toEqual([['1', '2']]);
  });

  it('treats HTML as literal text (no markup injection)', () => {
    const blocks = parseMarkdown('<img src=x onerror=alert(1)>');
    expect(blocks).toEqual([{ kind: 'paragraph', text: '<img src=x onerror=alert(1)>' }]);
  });
});
