import type { InstrumentSymbol } from './instruments';
import type { FeedStatus, Provenance } from './market';
import { isOpportunityStale, type Opportunity } from './opportunity';
import type { RiskProfile } from './risk';

/**
 * Contextual research notes derived ONLY from data the client holds.
 * Shared by the AI panel and the assistant so both say the same thing.
 */
export interface ResearchNote {
  key: string;
  title: string;
  detail: string;
}

/** Conditions under which the model's own analysis stops applying. */
export function invalidationNotes(o: Opportunity, confluence: readonly Opportunity[], nowMs: number, formatPrice: (v: number) => string): ResearchNote[] {
  if (o.status !== 'detected' || o.direction === 'neutral') return [];
  const notes: ResearchNote[] = [
    o.direction === 'long'
      ? { key: 'stop', title: 'Price trades below the stop-loss zone', detail: `Below ${formatPrice(o.stopLossZone.low)} — the model’s own invalidation level.` }
      : { key: 'stop', title: 'Price trades above the stop-loss zone', detail: `Above ${formatPrice(o.stopLossZone.high)} — the model’s own invalidation level.` },
    { key: 'horizon', title: 'Time runs out', detail: `The probability applies to the next ${o.horizonCandles} candles only.` },
    isOpportunityStale(o, nowMs)
      ? { key: 'stale', title: 'Already past its validity window', detail: 'Refresh before relying on it.' }
      : { key: 'expiry', title: 'The analysis expires', detail: 'After its validity time, newer candles may change the result.' },
  ];
  const opposing = confluence.filter((c) => c.timeframe !== o.timeframe && c.status === 'detected' && c.direction !== o.direction);
  if (opposing.length)
    notes.push({ key: 'tf', title: 'Other timeframes disagree', detail: `${opposing.map((c) => `${c.timeframe} reads ${c.direction}`).join(', ')}. Disagreement weakens the setup.` });
  const against = o.factors.filter((f) => f.contribution < 0);
  if (against.length) notes.push({ key: 'factors', title: 'Factors already against it', detail: `${against.map((f) => f.label).join(', ')}. If these strengthen, the case weakens.` });
  return notes;
}

export interface MissingInput {
  opportunity: Opportunity | null;
  priceProvenance: Provenance | null;
  feedStatus: FeedStatus | null;
  confluenceCount: number;
  /** null = the user has not shared it (assistant) — omit to skip risk notes (AI panel). */
  riskProfile?: RiskProfile | null;
  symbol: InstrumentSymbol | null;
  nowMs: number;
}

/** What is missing or unverified before the analysis can be evaluated. */
export function missingNotes(i: MissingInput): ResearchNote[] {
  const notes: ResearchNote[] = [];
  const o = i.opportunity;
  if (!o) notes.push({ key: 'no-output', title: 'No model output', detail: 'No analysis for the selected instrument and timeframe is loaded.' });
  else {
    if (o.provenance === 'demo') notes.push({ key: 'demo-model', title: 'The model output is simulated', detail: 'The trained model is not connected.' });
    if (o.status === 'detected' && !o.confidenceBand) notes.push({ key: 'band', title: 'No confidence band', detail: 'The model did not quantify the uncertainty of its probability.' });
    if (o.status === 'detected' && !o.forecast?.length) notes.push({ key: 'path', title: 'No projected path', detail: 'Only zones were returned, so no projection is drawn.' });
    if (o.expectedValueR === undefined) notes.push({ key: 'ev', title: 'No expected value', detail: 'The model did not supply one.' });
    if (isOpportunityStale(o, i.nowMs)) notes.push({ key: 'stale', title: 'The analysis is stale', detail: 'It is past its validity window.' });
  }
  if (i.priceProvenance === 'demo') notes.push({ key: 'demo-price', title: 'Prices are simulated', detail: 'Not a live market feed.' });
  if (i.feedStatus && !['live', 'demo'].includes(i.feedStatus)) notes.push({ key: 'feed', title: `The price feed is ${i.feedStatus}`, detail: 'Values may be out of date.' });
  if (i.confluenceCount === 0) notes.push({ key: 'tf', title: 'No other timeframes', detail: 'Nothing is available to confirm or contradict the signal.' });
  if (i.riskProfile === null) notes.push({ key: 'risk', title: 'Your risk profile is not shared', detail: 'Position size and limit checks cannot be evaluated.' });
  else if (i.riskProfile) {
    if (i.riskProfile.capital === null) notes.push({ key: 'capital', title: 'Account capital is not set', detail: 'Set it in Capital & risk to size trades.' });
    if (i.symbol && !i.riskProfile.contractSizes[i.symbol]) notes.push({ key: 'contract', title: 'No broker contract size', detail: 'Lots cannot be shown (units still can).' });
  }
  notes.push({ key: 'news', title: 'Economic calendar and news are not included', detail: 'Scheduled events can move price regardless of the model.' });
  return notes;
}
