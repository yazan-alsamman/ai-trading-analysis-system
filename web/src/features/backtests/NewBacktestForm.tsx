import { Play } from 'lucide-react';
import { useMemo, useState, type SyntheticEvent } from 'react';
import { useServices } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Checkbox, Field, FormError, Input, Select } from '@/components/ui/Form';
import { ErrorState } from '@/components/ui/StateViews';
import type { BacktestInput } from '@/domain/backtests';
import { BACKEND_TIMEFRAMES, isBackendTimeframe, type BackendTimeframe, type CustomStrategySummary, type ParamSpec, type StrategyDefinition, type StrategyParams } from '@/domain/strategies';
import { useResource } from '@/hooks/useResource';
import { isApiError, userMessage } from '@/services/errors';

const DAY = 86_400_000;
const isoDate = (ms: number) => new Date(ms).toISOString().slice(0, 10);

type Direction = '' | 'long_only' | 'long_short';

interface ConfigFields {
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
  direction: Direction;
  stopLossPct: string;
  takeProfitPct: string;
}

const EMPTY_CONFIG: ConfigFields = { initialCapital: '', feeBps: '', slippageBps: '', direction: '', stopLossPct: '', takeProfitPct: '' };

/** Engine config fields from docs/backtesting.md; blank fields take the server defaults. */
const CONFIG_LIMITS = {
  initialCapital: { min: 1, max: 1_000_000_000, label: 'Initial capital', hint: 'Server default 10,000 (quote currency)' },
  feeBps: { min: 0, max: 1000, label: 'Fee (bps per side)', hint: 'Server default 10 bps = 0.10 %' },
  slippageBps: { min: 0, max: 1000, label: 'Slippage (bps)', hint: 'Server default 5 bps, against you on every fill' },
  stopLossPct: { min: 0.01, max: 100, label: 'Stop loss (%)', hint: 'Optional percent stop from the entry' },
  takeProfitPct: { min: 0.01, max: 1000, label: 'Take profit (%)', hint: 'Optional percent target from the entry' },
} as const;

type NumericConfigKey = keyof typeof CONFIG_LIMITS;

function paramInitial(def: StrategyDefinition | undefined): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = {};
  for (const p of def?.params ?? []) {
    if (p.type === 'bool') out[p.name] = p.default === true;
    else out[p.name] = p.default === null ? '' : String(p.default);
  }
  return out;
}

function parseParam(spec: ParamSpec, raw: string | boolean | undefined): { value?: number | boolean | string; error?: string } {
  if (spec.type === 'bool') return { value: raw === true };
  const text = typeof raw === 'string' ? raw.trim() : '';
  if (text === '') return {};
  if (spec.type === 'int' || spec.type === 'float') {
    const n = Number(text);
    if (!Number.isFinite(n)) return { error: 'Enter a number.' };
    if (spec.type === 'int' && !Number.isInteger(n)) return { error: 'Enter a whole number.' };
    if (spec.min !== null && n < spec.min) return { error: `At least ${spec.min}.` };
    if (spec.max !== null && n > spec.max) return { error: `At most ${spec.max}.` };
    return { value: n };
  }
  return { value: text };
}

interface Props {
  catalog: StrategyDefinition[];
  custom: CustomStrategySummary[];
  onCreated: (id: string) => void;
  onCancel?: () => void;
}

/** Queues a backtest (POST /backtests). Validation mirrors the server; the server remains the authority. */
export function NewBacktestForm({ catalog, custom, onCreated, onCancel }: Props) {
  const services = useServices();
  const instruments = useResource('backtest-instruments', (signal) => services.instruments.list({ signal }));
  const activeInstruments = useMemo(() => (instruments.data ?? []).filter((i) => i.isActive), [instruments.data]);

  const today = isoDate(Date.now());
  const [strategyKey, setStrategyKey] = useState(catalog[0]?.key ?? custom[0]?.key ?? '');
  const [params, setParams] = useState<Record<string, string | boolean>>(() => paramInitial(catalog[0]));
  const [instrumentId, setInstrumentId] = useState('');
  const [timeframe, setTimeframe] = useState<BackendTimeframe>('1h');
  const [start, setStart] = useState(isoDate(Date.now() - 90 * DAY));
  const [end, setEnd] = useState(today);
  const [config, setConfig] = useState<ConfigFields>(EMPTY_CONFIG);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [serverFields, setServerFields] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const definition = catalog.find((s) => s.key === strategyKey);
  const selectedInstrument = instrumentId || activeInstruments[0]?.id || '';

  const chooseStrategy = (key: string) => {
    setStrategyKey(key);
    setParams(paramInitial(catalog.find((s) => s.key === key)));
    setErrors({});
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setServerFields([]);
    const next: Record<string, string> = {};

    if (!strategyKey) next.strategy = 'Choose a strategy.';
    if (!selectedInstrument) next.instrument = 'Choose an instrument.';

    const resolvedParams: StrategyParams = {};
    for (const spec of definition?.params ?? []) {
      const r = parseParam(spec, params[spec.name]);
      if (r.error) next[`param.${spec.name}`] = r.error;
      else if (r.value !== undefined) resolvedParams[spec.name] = r.value;
    }

    if (!start) next.start = 'Choose a start date.';
    if (!end) next.end = 'Choose an end date.';
    else if (end > today) next.end = 'The end cannot be in the future.';
    if (start && end && start >= end) next.start = 'The start must be before the end.';

    const engine: Record<string, unknown> = {};
    const exits: Record<string, unknown> = {};
    for (const key of Object.keys(CONFIG_LIMITS) as NumericConfigKey[]) {
      const text = config[key].trim();
      if (!text) continue;
      const n = Number(text);
      const lim = CONFIG_LIMITS[key];
      if (!Number.isFinite(n)) next[`config.${key}`] = 'Enter a number.';
      else if (n < lim.min || n > lim.max) next[`config.${key}`] = `Between ${lim.min} and ${lim.max.toLocaleString('en-US')}.`;
      else if (key === 'initialCapital') engine.initial_capital = n;
      else if (key === 'feeBps') engine.fee_bps = n;
      else if (key === 'slippageBps') engine.slippage_bps = n;
      // Documented aliases of a percent stop and a percent target (docs/backtesting.md).
      else if (key === 'stopLossPct') exits.stop_loss_pct = n;
      else exits.take_profit_pct = n;
    }
    if (config.direction) engine.direction = config.direction;
    if (Object.keys(exits).length) engine.exits = exits;

    setErrors(next);
    if (Object.keys(next).length) return;

    // The end date is inclusive; today's end is "now" so it is never in the future.
    const endMs = Math.min(Date.parse(`${end}T23:59:59Z`), Date.now() - 60_000);
    const input: BacktestInput = {
      instrumentId: selectedInstrument,
      timeframe,
      strategyKey,
      params: strategyKey.startsWith('custom:') ? {} : resolvedParams,
      start: `${start}T00:00:00Z`,
      end: new Date(endMs).toISOString(),
      config: Object.keys(engine).length ? engine : null,
    };

    setBusy(true);
    try {
      const created = await services.backtests.create(input);
      setConfig(EMPTY_CONFIG);
      onCreated(created.id);
    } catch (e) {
      setFormError(userMessage(e));
      if (isApiError(e) && e.kind === 'validation') setServerFields(Object.entries(e.fieldErrors).map(([field, msgs]) => `${field}: ${msgs.join(' ')}`));
    } finally {
      setBusy(false);
    }
  };

  const setConfigField = (key: keyof ConfigFields, value: string) => setConfig((c) => ({ ...c, [key]: value }));

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-5" aria-label="New backtest">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Strategy" error={errors.strategy}>
          {({ id, describedBy, invalid }) => (
            <Select id={id} aria-describedby={describedBy} invalid={invalid} value={strategyKey} onChange={(e) => chooseStrategy(e.target.value)}>
              {catalog.length > 0 && (
                <optgroup label="Strategy catalog">
                  {catalog.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.title}
                    </option>
                  ))}
                </optgroup>
              )}
              {custom.length > 0 && (
                <optgroup label="Your custom strategies">
                  {custom.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </Select>
          )}
        </Field>

        <Field label="Instrument" error={errors.instrument} {...(instruments.status === 'loading' ? { hint: 'Loading instruments…' } : {})}>
          {({ id, describedBy, invalid }) => (
            <Select
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              value={selectedInstrument}
              disabled={activeInstruments.length === 0}
              onChange={(e) => setInstrumentId(e.target.value)}
            >
              {activeInstruments.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.symbol} · {i.source}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {instruments.status === 'error' && <ErrorState error={instruments.error} onRetry={instruments.reload} title="Could not load instruments" compact className="sm:col-span-2" />}

        <Field label="Timeframe">
          {({ id, describedBy }) => (
            <Select id={id} aria-describedby={describedBy} value={timeframe} onChange={(e) => isBackendTimeframe(e.target.value) && setTimeframe(e.target.value)}>
              {BACKEND_TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Start (UTC)" error={errors.start}>
            {({ id, describedBy, invalid }) => (
              <Input id={id} type="date" aria-describedby={describedBy} invalid={invalid} value={start} max={end || today} onChange={(e) => setStart(e.target.value)} />
            )}
          </Field>
          <Field label="End (UTC)" error={errors.end}>
            {({ id, describedBy, invalid }) => (
              <Input id={id} type="date" aria-describedby={describedBy} invalid={invalid} value={end} max={today} onChange={(e) => setEnd(e.target.value)} />
            )}
          </Field>
        </div>
      </div>

      {strategyKey.startsWith('custom:') ? (
        <p className="text-xs text-fg-3">Custom strategies run with their saved definition; the server stores a snapshot so the result stays reproducible.</p>
      ) : (
        definition &&
        definition.params.length > 0 && (
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 text-sm font-medium text-fg">Strategy parameters</legend>
            <div className="grid gap-4 sm:grid-cols-3">
              {definition.params.map((spec) =>
                spec.type === 'bool' ? (
                  <Checkbox
                    key={spec.name}
                    label={spec.title}
                    checked={params[spec.name] === true}
                    onChange={(e) => setParams((p) => ({ ...p, [spec.name]: e.target.checked }))}
                    className="self-end pb-2"
                  />
                ) : (
                  <Field
                    key={spec.name}
                    label={spec.title}
                    error={errors[`param.${spec.name}`]}
                    {...(spec.min !== null || spec.max !== null ? { hint: `${spec.min ?? '…'} – ${spec.max ?? '…'}` } : {})}
                  >
                    {({ id, describedBy, invalid }) => (
                      <Input
                        id={id}
                        aria-describedby={describedBy}
                        invalid={invalid}
                        inputMode="decimal"
                        type={spec.type === 'int' || spec.type === 'float' ? 'number' : 'text'}
                        step={spec.type === 'int' ? 1 : 'any'}
                        {...(spec.min !== null ? { min: spec.min } : {})}
                        {...(spec.max !== null ? { max: spec.max } : {})}
                        value={typeof params[spec.name] === 'string' ? (params[spec.name] as string) : ''}
                        onChange={(e) => setParams((p) => ({ ...p, [spec.name]: e.target.value }))}
                      />
                    )}
                  </Field>
                ),
              )}
            </div>
          </fieldset>
        )
      )}

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-medium text-fg">
          Engine settings <span className="font-normal text-fg-3">(optional — blank uses the server defaults)</span>
        </legend>
        <div className="grid gap-4 sm:grid-cols-3">
          {(Object.keys(CONFIG_LIMITS) as NumericConfigKey[]).map((key) => (
            <Field key={key} label={CONFIG_LIMITS[key].label} hint={CONFIG_LIMITS[key].hint} error={errors[`config.${key}`]}>
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  type="number"
                  inputMode="decimal"
                  step="any"
                  min={CONFIG_LIMITS[key].min}
                  max={CONFIG_LIMITS[key].max}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  value={config[key]}
                  onChange={(e) => setConfigField(key, e.target.value)}
                />
              )}
            </Field>
          ))}
          <Field label="Direction" hint="Long only: sells only close longs">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={config.direction} onChange={(e) => setConfigField('direction', e.target.value)}>
                <option value="">Server default (long only)</option>
                <option value="long_only">Long only</option>
                <option value="long_short">Long and short</option>
              </Select>
            )}
          </Field>
        </div>
      </fieldset>

      <FormError message={formError} />
      {serverFields.length > 0 && (
        <ul className="-mt-3 list-disc pl-5 text-xs text-danger">
          {serverFields.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        {onCancel && (
          <Button onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" icon={Play} loading={busy} disabled={!strategyKey || !selectedInstrument}>
          Run backtest
        </Button>
      </div>
    </form>
  );
}
