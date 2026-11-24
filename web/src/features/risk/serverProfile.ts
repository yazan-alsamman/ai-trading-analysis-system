import type { RiskProfile } from '@/domain/risk';
import type { ServerRiskProfile } from '@/services/types';

const same = (a: number | null, b: number | null) => a !== null && b !== null && Math.abs(a - b) < 1e-9;

/** Whether the browser's saved profile matches the server's on the fields both sides have. */
export function profilesMatch(local: RiskProfile, server: ServerRiskProfile): boolean {
  return same(local.capital, server.capital) && local.currency === server.currency && same(local.maxRiskPerTradePct, server.riskPerTradePct) && same(local.dailyLossLimitPct, server.dailyLossLimitPct);
}
