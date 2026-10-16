import { beforeEach, describe, expect, it } from 'vitest';
import { membershipStore } from '@/app/membershipStore';
import { stepAt, stickyProgress, segment } from '@/motion/tokens';
import { buildShowcase, SHOWCASE_PROFILE } from '@/marketing/showcase';
import { addedOver, FEATURE_IDS, FEATURES, formatPrice, getPlan, isPlanId, lowestPlanWith, planIncludes, PLANS, suggestPlan } from './membership';

describe('membership configuration', () => {
  it('defines every feature for every plan, with a status for every feature', () => {
    for (const plan of PLANS) expect(Object.keys(plan.access).sort()).toEqual([...FEATURE_IDS].sort());
    expect(FEATURES.map((f) => f.id).sort()).toEqual([...FEATURE_IDS].sort());
  });

  it('invents no prices and offers no activation', () => {
    for (const plan of PLANS) {
      expect(plan.price.kind).toBe('tba');
      expect(formatPrice(plan.price)).toBe('Pricing to be announced');
      expect(plan.activation).toBe('unavailable');
    }
  });

  it('keeps transparency and risk tools in every tier', () => {
    for (const plan of PLANS) {
      expect(planIncludes(plan.id, 'analytics')).toBe(true);
      expect(planIncludes(plan.id, 'risk_tools')).toBe(true);
    }
  });

  it('is cumulative: a higher tier never loses a feature', () => {
    for (const f of FEATURE_IDS) {
      const order = PLANS.map((p) => planIncludes(p.id, f));
      expect(order, f).toEqual([...order].sort((a, b) => Number(a) - Number(b)));
    }
  });

  it('describes upgrades and gated features', () => {
    expect(addedOver('essential', 'professional')).toEqual(['instruments', 'tf_alignment', 'signal_filters', 'watchlist', 'alert_delivery', 'saved_workspaces']);
    expect(addedOver('professional', 'elite')).toEqual(['assistant', 'research_history']);
    expect(lowestPlanWith('assistant')?.id).toBe('elite');
    expect(getPlan('essential').access.instruments).toBe('Gold (XAU/USD)');
  });

  it('suggests the smallest plan that covers the stated needs', () => {
    expect(suggestPlan({ instruments: 'gold', personalise: false, assistant: false })).toBe('essential');
    expect(suggestPlan({ instruments: 'gold_fx', personalise: false, assistant: false })).toBe('professional');
    expect(suggestPlan({ instruments: 'gold', personalise: true, assistant: false })).toBe('professional');
    expect(suggestPlan({ instruments: 'gold', personalise: false, assistant: true })).toBe('elite');
  });

  it('validates plan ids from URLs', () => {
    expect(isPlanId('elite')).toBe(true);
    expect(isPlanId('platinum')).toBe(false);
    expect(isPlanId(null)).toBe(false);
  });
});

describe('membership store (frontend demo state)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    membershipStore.resetForTests();
  });

  it('keeps the selected plan for the sign-up journey and ignores tampered values', () => {
    membershipStore.select('professional');
    membershipStore.resetForTests();
    expect(membershipStore.getSelected()).toBe('professional');
    sessionStorage.setItem('ata.membership.selected.v1', JSON.stringify({ plan: 'platinum', at: 1 }));
    membershipStore.resetForTests();
    expect(membershipStore.getSelected()).toBeNull();
  });

  it('labels the in-app membership as a demo and can clear it', () => {
    membershipStore.activateDemo('elite');
    expect(membershipStore.getDemo()).toMatchObject({ plan: 'elite', demo: true });
    membershipStore.clearDemo();
    expect(membershipStore.getDemo()).toBeNull();
  });
});

describe('motion maths', () => {
  it('maps a pinned section to 0–1 progress and steps', () => {
    expect(stickyProgress(0, 3000, 1000)).toBe(0);
    expect(stickyProgress(-1000, 3000, 1000)).toBe(0.5);
    expect(stickyProgress(-5000, 3000, 1000)).toBe(1);
    expect(stickyProgress(400, 3000, 1000)).toBe(0);
    expect(stepAt(0.999, 7)).toBe(6);
    expect(stepAt(0, 7)).toBe(0);
    expect(segment(0.5, 0.25, 0.75)).toBe(0.5);
    expect(segment(0.9, 0.25, 0.75)).toBe(1);
  });
});

describe('public showcase', () => {
  it('is built from the demo fixtures at a fixed anchor and is self-consistent', () => {
    const s = buildShowcase();
    expect(s.opportunity.provenance).toBe('demo');
    expect(s.opportunity.status).toBe('detected');
    expect(s.opportunity.forecast?.length).toBeGreaterThan(0);
    // Projection points are strictly after the last observed candle (never drawn as observed data).
    const lastObserved = s.candles[s.candles.length - 1]?.time ?? 0;
    expect(s.opportunity.forecast?.every((f) => f.time > lastObserved)).toBe(true);
    expect(s.risk.riskBudget).toBeCloseTo((SHOWCASE_PROFILE.capital ?? 0) * 0.01, 6);
    expect(s.assistant.provider).toBe('demo-rules');
  });
});
