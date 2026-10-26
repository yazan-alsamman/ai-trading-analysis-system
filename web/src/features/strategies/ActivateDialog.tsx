import { useState } from 'react';
import { useServices } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select } from '@/components/ui/Form';
import {
  BACKEND_TIMEFRAMES,
  isBackendTimeframe,
  type BackendInstrument,
  type BackendTimeframe,
  type CustomStrategySummary,
  type StrategyActivation,
  type StrategyDefinition,
  type StrategyParams,
} from '@/domain/strategies';
import { ParamFields } from './ParamFields';
import { defaultInstrument, errorText, paramDraft, parseParams, type ParamDraft } from './strategyUtils';

export interface ActivatePreset {
  strategyKey: string;
  params?: StrategyParams;
  instrumentId?: string;
  timeframe?: BackendTimeframe;
}

interface Props {
  open: boolean;
  preset: ActivatePreset | null;
  catalog: readonly StrategyDefinition[];
  custom: readonly CustomStrategySummary[];
  instruments: readonly BackendInstrument[];
  onClose: () => void;
  onActivated: (activation: StrategyActivation) => void;
}

/** Start the live engine on a strategy for one instrument and timeframe (POST /me/strategies). */
export function ActivateDialog({ open, preset, catalog, custom, instruments, onClose, onActivated }: Props) {
  const services = useServices();
  const firstKey = preset?.strategyKey ?? catalog[0]?.key ?? custom[0]?.key ?? '';
  const [strategyKey, setStrategyKey] = useState(firstKey);
  const [instrumentId, setInstrumentId] = useState(preset?.instrumentId ?? defaultInstrument(instruments));
  const [timeframe, setTimeframe] = useState<BackendTimeframe>(preset?.timeframe ?? '1h');
  const [name, setName] = useState('');
  const [notify, setNotify] = useState(true);
  const [draft, setDraft] = useState<ParamDraft>(() => paramDraft(catalog.find((s) => s.key === firstKey)?.params ?? [], preset?.params));
  const [paramErrors, setParamErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Re-seed the form whenever the dialog is opened with a new preset.
  const [lastPreset, setLastPreset] = useState(preset);
  if (preset !== lastPreset) {
    setLastPreset(preset);
    const key = preset?.strategyKey ?? catalog[0]?.key ?? custom[0]?.key ?? '';
    setStrategyKey(key);
    setInstrumentId(preset?.instrumentId ?? defaultInstrument(instruments));
    setTimeframe(preset?.timeframe ?? '1h');
    setName('');
    setNotify(true);
    setDraft(paramDraft(catalog.find((s) => s.key === key)?.params ?? [], preset?.params));
    setParamErrors({});
    setError(null);
  }

  const def = catalog.find((s) => s.key === strategyKey);
  const specs = def?.params ?? [];
  const activeInstruments = instruments.filter((i) => i.isActive);

  const changeStrategy = (key: string) => {
    setStrategyKey(key);
    setDraft(paramDraft(catalog.find((s) => s.key === key)?.params ?? []));
    setParamErrors({});
  };

  const submit = async () => {
    setError(null);
    if (!strategyKey) return setError('Choose a strategy.');
    if (!instrumentId) return setError('Choose an instrument.');
    const { params, errors } = parseParams(specs, draft);
    setParamErrors(errors);
    if (Object.keys(errors).length) return;
    setBusy(true);
    try {
      const activation = await services.strategies.activate({
        strategyKey,
        instrumentId,
        timeframe,
        params,
        name: name.trim() || null,
        isActive: true,
        notify,
      });
      onActivated(activation);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Activate strategy"
      description="The server evaluates the strategy on every closed bar and records a signal when its rules hold. It never places a trade."
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="activate-strategy-form" loading={busy}>
            Activate
          </Button>
        </>
      }
    >
      <form
        id="activate-strategy-form"
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <FormError message={error} />
        <Field label="Strategy">
          {({ id, describedBy }) => (
            <Select id={id} aria-describedby={describedBy} value={strategyKey} onChange={(e) => changeStrategy(e.target.value)}>
              <optgroup label="Platform strategies">
                {catalog.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.title}
                  </option>
                ))}
              </optgroup>
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
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Instrument">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
                {activeInstruments.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.symbol} · {i.market}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Timeframe">
            {({ id, describedBy }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                value={timeframe}
                onChange={(e) => {
                  if (isBackendTimeframe(e.target.value)) setTimeframe(e.target.value);
                }}
              >
                {BACKEND_TIMEFRAMES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-medium text-fg">Parameters</legend>
          {strategyKey.startsWith('custom:') ? (
            <p className="text-sm text-fg-3">Custom strategies carry their rules in their definition and take no parameters here.</p>
          ) : (
            <ParamFields specs={specs} draft={draft} errors={paramErrors} onChange={setDraft} />
          )}
        </fieldset>
        <Field label="Name" optional hint="Shown in your list and in notifications.">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Checkbox label="Notify me when it signals" description="Delivered according to your notification preferences." checked={notify} onChange={(e) => setNotify(e.target.checked)} />
      </form>
    </Dialog>
  );
}
