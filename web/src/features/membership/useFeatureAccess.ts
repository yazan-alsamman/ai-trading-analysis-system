import { useDemoMembership } from '@/app/membershipStore';
import { getPlan, planIncludes, type FeatureId } from '@/domain/membership';

/**
 * Plan-aware UI for the DEMO membership only. With no demo plan selected,
 * everything is open (the demo shows the whole product). This is a preview of
 * the experience, never authorisation — enforcement belongs on the server.
 */
export function useFeatureAccess(feature: FeatureId): { allowed: boolean; planName: string | null } {
  const demo = useDemoMembership();
  if (!demo) return { allowed: true, planName: null };
  return { allowed: planIncludes(demo.plan, feature), planName: getPlan(demo.plan).name };
}

