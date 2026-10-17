import { CircleCheck, OctagonX, TriangleAlert } from 'lucide-react';
import type { LimitStatus } from '@/domain/risk';

/** Words + icon for each limit status (never colour alone). */
export const STATUS_META: Record<LimitStatus, { label: string; icon: typeof CircleCheck; text: string; bar: string }> = {
  ok: { label: 'Within limit', icon: CircleCheck, text: 'text-fg-2', bar: 'bg-fg-3' },
  caution: { label: 'Near limit', icon: TriangleAlert, text: 'text-warning', bar: 'bg-warning' },
  breach: { label: 'Breach', icon: OctagonX, text: 'text-danger', bar: 'bg-danger' },
};
