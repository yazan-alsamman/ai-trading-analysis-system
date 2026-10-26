import type { JsonObject } from '@/domain/admin';
import { MISSING } from '@/lib/format';

/**
 * Safe readers for the backend's status blocks (shape owned by the backend,
 * docs/security.md): a missing or differently typed field shows "—", never a
 * guessed value.
 */
export function rec(value: unknown): JsonObject | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonObject) : null;
}

export function list(value: unknown): JsonObject[] {
  return Array.isArray(value) ? value.filter((v): v is JsonObject => rec(v) !== null) : [];
}

export function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function text(value: unknown): string {
  if (value === null || value === undefined || value === '') return MISSING;
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

/** 93784 s → "1d 2h 3m". */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return MISSING;
  const s = Math.max(0, Math.round(seconds));
  const d = Math.floor(s / 86_400);
  const h = Math.floor((s % 86_400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

export function sumValues(value: unknown): number | null {
  const r = rec(value);
  if (!r) return null;
  return Object.values(r).reduce<number>((acc, v) => acc + (num(v) ?? 0), 0);
}

/** Badge tone for a status word the backend uses (ok, degraded, no_data, closed, error…). */
export function statusTone(status: unknown): 'up' | 'warning' | 'danger' | 'neutral' {
  if (status === 'ok' || status === true) return 'up';
  if (status === 'closed' || status === 'unknown' || status === 'disabled') return 'neutral';
  if (status === 'degraded' || status === 'not_ready') return 'warning';
  return 'danger';
}
