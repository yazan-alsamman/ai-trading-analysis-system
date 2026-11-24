import type { BadgeTone } from '@/components/ui/Badge';
import type { BackendInstrument } from '@/domain/strategies';
import type { SetupState } from '@/domain/aiSetups';
import { formatNumber, formatPrice, MISSING } from '@/lib/format';

export const STATE_TONE: Record<SetupState, BadgeTone> = {
  DEVELOPING: 'neutral',
  ARMED: 'accent',
  ACTIVE: 'info',
  CLOSED: 'neutral',
  EXPIRED: 'neutral',
  INVALIDATED: 'warning',
};

/** Shown wherever a model-only value is null (v1 runs the rules alone). */
export const NO_MODEL_HINT = 'Needs a trained model. Version 1 of the AI engine runs its setup rules only, so this is not provided.';

/** A price at the instrument's precision (the backend's; 2 decimals when unknown). */
export function formatSetupPrice(value: number | null, precision: number | null | undefined): string {
  return value === null ? MISSING : formatPrice(value, precision ?? 2);
}

export function formatR(value: number | null): string {
  return value === null ? MISSING : `${value > 0 ? '+' : ''}${formatNumber(value, 2)}R`;
}

export function instrumentLabel(id: string, instruments: readonly BackendInstrument[] | undefined): string {
  return instruments?.find((i) => i.id === id)?.symbol ?? 'Unknown instrument';
}
