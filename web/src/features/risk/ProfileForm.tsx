import { ChevronRight, RotateCcw, Save } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { usePreferences, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select } from '@/components/ui/Form';
import { SourceTag } from '@/components/ui/SourceTag';
import { INSTRUMENTS, type InstrumentSymbol } from '@/domain/instruments';
import { ACCOUNT_CURRENCIES, validateRiskProfile, type AccountCurrency, type RiskProfile } from '@/domain/risk';
import { numberError, parseDecimal } from './parse';

type Draft = Record<
  'capital' | 'maxRiskPerTradePct' | 'dailyLossLimitPct' | 'maxOpenRiskPct' | 'maxOpenPositions' | 'openRisk' | 'realisedLossToday' | 'openPositions' | 'volumeStep',
  string
> & { currency: AccountCurrency; contractSizes: Partial<Record<InstrumentSymbol, string>> };

const str = (v: number | null) => (v === null ? '' : String(v));

function toDraft(p: RiskProfile): Draft {
  return {
    capital: str(p.capital),
    currency: p.currency,
    maxRiskPerTradePct: str(p.maxRiskPerTradePct),
    dailyLossLimitPct: str(p.dailyLossLimitPct),
    maxOpenRiskPct: str(p.maxOpenRiskPct),
    maxOpenPositions: str(p.maxOpenPositions),
    openRisk: str(p.openRisk),
    realisedLossToday: str(p.realisedLossToday),
    openPositions: str(p.openPositions),
    volumeStep: str(p.volumeStep),
    contractSizes: Object.fromEntries(Object.entries(p.contractSizes).map(([k, v]) => [k, String(v)])),
  };
}

type Errors = Partial<Record<keyof Draft | `cs_${InstrumentSymbol}`, string>>;

function fromDraft(d: Draft): { profile: RiskProfile | null; errors: Errors } {
  const errors: Errors = {};
  const num = (key: keyof Draft, label: string, o: { required?: boolean; min?: number; max?: number; integer?: boolean } = {}) => {
    const v = parseDecimal(d[key] as string);
    const e = numberError(v, { label, ...o });
    if (e) errors[key] = e;
    return v;
  };
  const capital = num('capital', 'your capital', { min: 0 });
  const perTrade = num('maxRiskPerTradePct', 'risk per trade', { required: true, max: 100 });
  const daily = num('dailyLossLimitPct', 'the daily loss limit', { required: true, max: 100 });
  const open = num('maxOpenRiskPct', 'the open-risk limit', { required: true, max: 100 });
  const maxPos = num('maxOpenPositions', 'maximum positions', { required: true, integer: true, min: 1, max: 50 });
  const openRisk = num('openRisk', 'open risk', { min: 0 });
  const realised = num('realisedLossToday', 'today’s realised loss', { min: 0 });
  const openPos = num('openPositions', 'open positions', { integer: true, min: 0 });
  const step = num('volumeStep', 'the volume step', { min: 0 });
  const contractSizes: Partial<Record<InstrumentSymbol, number>> = {};
  for (const [sym, raw] of Object.entries(d.contractSizes) as [InstrumentSymbol, string][]) {
    const v = parseDecimal(raw);
    if (v === null) continue;
    if (Number.isNaN(v) || v <= 0) errors[`cs_${sym}`] = 'Enter a positive number of units per lot.';
    else contractSizes[sym] = v;
  }
  if (Object.keys(errors).length > 0) return { profile: null, errors };
  const profile: RiskProfile = {
    capital: capital === 0 ? null : capital,
    currency: d.currency,
    maxRiskPerTradePct: perTrade ?? 1,
    dailyLossLimitPct: daily ?? 3,
    maxOpenRiskPct: open ?? 5,
    maxOpenPositions: maxPos ?? 3,
    openRisk: openRisk ?? 0,
    realisedLossToday: realised ?? 0,
    openPositions: openPos ?? 0,
    contractSizes,
    volumeStep: step === 0 ? null : step,
  };
  const domainErrors = validateRiskProfile(profile);
  return { profile: Object.keys(domainErrors).length ? null : profile, errors: domainErrors as Errors };
}

function Group({ title, tag, description, children }: { title: string; tag?: React.ReactNode; description: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <legend className="contents">
        <span className="flex items-center gap-2 text-sm font-semibold text-fg">
          {title} {tag}
        </span>
      </legend>
      <p className="-mt-1.5 text-xs text-fg-3">{description}</p>
      {children}
    </fieldset>
  );
}

export function ProfileForm() {
  const { prefs, setRiskProfile } = usePreferences();
  const { notify } = useToast();
  const saved = prefs.riskProfile;
  const [draft, setDraft] = useState<Draft>(() => toDraft(saved));
  const [errors, setErrors] = useState<Errors>({});
  useEffect(() => setDraft(toDraft(saved)), [saved]);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(toDraft(saved)), [draft, saved]);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const text = (key: Exclude<keyof Draft, 'currency' | 'contractSizes'>, label: string, hint?: string, suffix?: string) => (
    <Field label={label} {...(hint ? { hint } : {})} error={errors[key]}>
      {({ id, describedBy, invalid }) => (
        <div className="relative">
          <Input
            id={id}
            inputMode="decimal"
            autoComplete="off"
            aria-describedby={describedBy}
            invalid={invalid}
            value={draft[key]}
            onChange={(e) => set(key, e.target.value)}
            className={suffix ? 'num pr-12' : 'num'}
          />
          {suffix && <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-fg-3">{suffix}</span>}
        </div>
      )}
    </Field>
  );

  const save = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    const { profile, errors: errs } = fromDraft(draft);
    setErrors(errs);
    if (!profile) {
      notify('Some fields need attention.', 'warning');
      return;
    }
    setRiskProfile(profile);
    notify('Risk profile saved in this browser.', 'success');
  };

  return (
    <form noValidate onSubmit={save} aria-label="Risk profile" className="flex flex-col gap-5">
      <Group title="Account" tag={<SourceTag kind="user" />} description="Used for every position size and limit. Not verified by the platform.">
        <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
          {text('capital', 'Account capital', 'Your equity. Leave empty until you want sizing.', draft.currency)}
          <Field label="Currency">
            {({ id }) => (
              <Select id={id} value={draft.currency} onChange={(e) => set('currency', e.target.value as AccountCurrency)}>
                {ACCOUNT_CURRENCIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      </Group>

      <Group title="Limits" description="Your rules. Every planned trade is checked against them.">
        <div className="grid gap-3 sm:grid-cols-2">
          {text('maxRiskPerTradePct', 'Max risk per trade', undefined, '%')}
          {text('dailyLossLimitPct', 'Daily loss limit', undefined, '%')}
          {text('maxOpenRiskPct', 'Max aggregate open risk', undefined, '%')}
          {text('maxOpenPositions', 'Max concurrent positions')}
        </div>
      </Group>

      <Group
        title="Current exposure"
        tag={<Badge>Reported by you</Badge>}
        description="This platform never executes or tracks trades, so it cannot know your open positions. Update these when they change."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {text('openRisk', 'Open risk', 'If every open stop is hit', draft.currency)}
          {text('realisedLossToday', 'Lost today', 'Realised losses', draft.currency)}
          {text('openPositions', 'Positions', 'Currently open')}
        </div>
      </Group>

      <details className="group border-t border-line pt-4">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm font-semibold text-fg">
          <ChevronRight aria-hidden className="size-4 transition-transform group-open:rotate-90" />
          Broker specification <span className="font-normal text-fg-3">(optional — enables lots)</span>
        </summary>
        <p className="mt-2 text-xs text-fg-3">
          Contract sizes differ between brokers (e.g. gold is often 100 oz per lot, but not always). The platform does not guess them: copy them from your
          broker’s contract specification. Without them, sizes are shown in units (ounces, currency units) only.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {INSTRUMENTS.map((i) => (
            <Field key={i.symbol} label={`${i.display} units per lot`} optional error={errors[`cs_${i.symbol}`]}>
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  inputMode="decimal"
                  className="num"
                  aria-describedby={describedBy}
                  invalid={invalid}
                  placeholder={i.kind === 'metal' ? 'e.g. from broker spec' : 'e.g. 100000'}
                  value={draft.contractSizes[i.symbol] ?? ''}
                  onChange={(e) => set('contractSizes', { ...draft.contractSizes, [i.symbol]: e.target.value })}
                />
              )}
            </Field>
          ))}
          {text('volumeStep', 'Volume step (lots)', 'Smallest lot increment, e.g. 0.01. Sizes are rounded down to it.')}
        </div>
      </details>

      <div className="sticky bottom-0 -mx-4 flex items-center justify-end gap-2 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:-mx-5 sm:px-5">
        {dirty && <span className="mr-auto text-xs text-warning">Unsaved changes — calculations use the saved profile.</span>}
        <Button
          variant="ghost"
          icon={RotateCcw}
          disabled={!dirty}
          onClick={() => {
            setDraft(toDraft(saved));
            setErrors({});
          }}
        >
          Discard
        </Button>
        <Button type="submit" variant="primary" icon={Save} disabled={!dirty}>
          Save profile
        </Button>
      </div>
    </form>
  );
}
