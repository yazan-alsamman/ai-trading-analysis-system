import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { membershipStore, useSelectedPlan } from '@/app/membershipStore';
import { isPlanId, type PlanId } from '@/domain/membership';

/**
 * The plan chosen earlier in the journey: `?plan=` (validated) wins and is
 * remembered; otherwise the session selection. Display only — never access.
 */
export function useJourneyPlan(): PlanId | null {
  const [params] = useSearchParams();
  const fromUrl = params.get('plan');
  const stored = useSelectedPlan();
  useEffect(() => {
    if (isPlanId(fromUrl) && fromUrl !== membershipStore.getSelected()) membershipStore.select(fromUrl);
  }, [fromUrl]);
  return isPlanId(fromUrl) ? fromUrl : stored;
}
