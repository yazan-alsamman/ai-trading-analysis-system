import type { PostDirection, PostVisibility } from '@/domain/social';

/* Formatting of server-owned JSON shown generically (e.g. an expert's signal feed). */

/** "snake_case_key" → "Snake case key", for server-owned JSON shown generically. */
export function humanizeKey(key: string): string {
  const text = key.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

export const DIRECTION_LABELS: Record<PostDirection, string> = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral' };

export const VISIBILITY_LABELS: Record<PostVisibility, string> = { public: 'Public', followers: 'Followers only', subscribers: 'Subscribers only' };
