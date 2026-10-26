import type { BackendInstrument, ParamSpec, StrategyParams } from '@/domain/strategies';
import { formatNumber } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';

/** The server's message plus its field-level reasons, for forms and toasts. */
export function errorText(error: unknown): string {
  const base = userMessage(error);
  if (!isApiError(error)) return base;
  const details = Object.entries(error.fieldErrors).flatMap(([field, msgs]) => msgs.map((m) => (field === 'form' ? m : `${field}: ${m}`)));
  return details.length ? `${base} ${details.join(' · ')}` : base;
}

export function defaultInstrument(instruments: readonly BackendInstrument[]): string {
  const active = instruments.filter((i) => i.isActive);
  return (active.find((i) => i.webSymbol) ?? active[0] ?? instruments[0])?.id ?? '';
}

export function instrumentLabel(id: string, instruments: readonly BackendInstrument[] | undefined): string {
  return instruments?.find((i) => i.id === id)?.symbol ?? 'Unknown instrument';
}

/* ---------------------------------------------------------------- params */

/** Form values of the parameter inputs: text for numbers, booleans as is. */
export type ParamDraft = Record<string, string | boolean>;

export const isBool = (p: ParamSpec) => p.type === 'bool' || typeof p.default === 'boolean';

export function paramDraft(specs: readonly ParamSpec[], values: StrategyParams = {}): ParamDraft {
  const out: ParamDraft = {};
  for (const p of specs) {
    const v = values[p.name] ?? p.default;
    if (isBool(p)) out[p.name] = v === true;
    else out[p.name] = v === null || v === undefined ? '' : String(v);
  }
  return out;
}

/** Parses and range-checks the inputs like the server does (int/float with min/max). */
export function parseParams(specs: readonly ParamSpec[], draft: ParamDraft): { params: StrategyParams; errors: Record<string, string> } {
  const params: StrategyParams = {};
  const errors: Record<string, string> = {};
  for (const p of specs) {
    const raw = draft[p.name];
    if (isBool(p)) {
      params[p.name] = raw === true;
      continue;
    }
    const text = typeof raw === 'string' ? raw.trim() : '';
    if (text === '') {
      if (p.default === null) errors[p.name] = 'Enter a value.';
      continue; // omitted → the server uses the default
    }
    const n = Number(text);
    if (!Number.isFinite(n)) errors[p.name] = 'Enter a number.';
    else if (p.type === 'int' && !Number.isInteger(n)) errors[p.name] = 'Enter a whole number.';
    else if (p.min !== null && n < p.min) errors[p.name] = `Minimum ${formatNumber(p.min, p.type === 'int' ? 0 : 2)}.`;
    else if (p.max !== null && n > p.max) errors[p.name] = `Maximum ${formatNumber(p.max, p.type === 'int' ? 0 : 2)}.`;
    else params[p.name] = n;
  }
  return { params, errors };
}

/** Generic key/value rendering of a server JSON object (signal details, plans). */
export function formatJsonValue(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : formatNumber(v, 5).replace(/\.?0+$/, '');
  if (typeof v === 'string' || typeof v === 'boolean') return String(v);
  return JSON.stringify(v);
}

export const humanize = (key: string) => key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

/* ------------------------------------------------------------- templates */

/** A valid builder definition (docs/custom-strategies.md: the ma_crossover replica). */
export const BUILDER_TEMPLATE = {
  schema_version: 1,
  category: 'trend',
  strength: 'fixed',
  buy: {
    all: [
      {
        left: { type: 'indicator', name: 'ema', params: { length: 9 } },
        op: 'crosses_above',
        right: { type: 'indicator', name: 'ema', params: { length: 21 } },
      },
    ],
  },
  sell: {
    all: [
      {
        left: { type: 'indicator', name: 'ema', params: { length: 9 } },
        op: 'crosses_below',
        right: { type: 'indicator', name: 'ema', params: { length: 21 } },
      },
    ],
  },
};

/** A composite of two global strategies; `refs` come from the builder catalog when available. */
export function compositeTemplate(refs: readonly string[]) {
  const [a = 'ma_crossover', b = 'rsi_reversal'] = refs;
  return {
    schema_version: 1,
    members: [
      { ref: a, weight: 1 },
      { ref: b, weight: 1 },
    ],
    mode: 'weighted',
    window: 3,
    threshold: 0.5,
  };
}
