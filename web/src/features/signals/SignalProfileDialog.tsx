import { useEffect, useState } from 'react';
import { usePreferences, useToast } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, Select, Switch } from '@/components/ui/Form';
import { INSTRUMENTS, type InstrumentSymbol } from '@/domain/instruments';
import { TIMEFRAMES, type Timeframe } from '@/domain/market';
import { isValidSignalProfile, type SignalProfile } from '@/domain/signalProfile';
import { formatPercent, formatRiskReward } from '@/lib/format';

const PROBABILITIES = [0, 0.55, 0.6, 0.65, 0.7, 0.75];
const RATIOS = [0, 1, 1.5, 2, 2.5, 3];

function toggle<T>(list: readonly T[], item: T, on: boolean): T[] {
  return on ? [...new Set([...list, item])] : list.filter((x) => x !== item);
}

/** Edit the saved filter that defines "For you". Saved in this browser. */
export function SignalProfileDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { prefs, setSignalProfile } = usePreferences();
  const { notify } = useToast();
  const [draft, setDraft] = useState<SignalProfile>(prefs.signalProfile);
  useEffect(() => {
    if (open) setDraft(prefs.signalProfile);
  }, [open, prefs.signalProfile]);
  const valid = isValidSignalProfile(draft);

  const save = () => {
    if (!valid) return;
    setSignalProfile(draft);
    notify('Signal profile saved.', 'success');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="Your signal profile"
      description="Applied to what the model returns — it never changes a model output. Saved in this browser."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} disabled={!valid}>
            Save profile
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Instruments</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {INSTRUMENTS.map((i) => (
              <Checkbox
                key={i.symbol}
                label={i.display}
                checked={draft.symbols.includes(i.symbol)}
                onChange={(e) => setDraft((d) => ({ ...d, symbols: toggle<InstrumentSymbol>(d.symbols, i.symbol, e.target.checked) }))}
              />
            ))}
          </div>
          {draft.symbols.length === 0 && <p className="mt-1.5 text-xs text-danger">Choose at least one instrument.</p>}
        </fieldset>
        <div className="grid gap-5 sm:grid-cols-2">
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-fg">Timeframes</legend>
            <div className="flex gap-4">
              {TIMEFRAMES.map((t) => (
                <Checkbox
                  key={t.id}
                  label={t.label}
                  checked={draft.timeframes.includes(t.id)}
                  onChange={(e) => setDraft((d) => ({ ...d, timeframes: toggle<Timeframe>(d.timeframes, t.id, e.target.checked) }))}
                />
              ))}
            </div>
            {draft.timeframes.length === 0 && <p className="mt-1.5 text-xs text-danger">Choose at least one timeframe.</p>}
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-fg">Directions</legend>
            <div className="flex gap-4">
              {(['long', 'short'] as const).map((d) => (
                <Checkbox
                  key={d}
                  label={d === 'long' ? 'Long' : 'Short'}
                  checked={draft.directions.includes(d)}
                  onChange={(e) => setDraft((p) => ({ ...p, directions: toggle(p.directions, d, e.target.checked) }))}
                />
              ))}
            </div>
            {draft.directions.length === 0 && <p className="mt-1.5 text-xs text-danger">Choose at least one direction.</p>}
          </fieldset>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Minimum probability" hint="The model’s probability that the target is reached before the stop.">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={String(draft.minProbability)} onChange={(e) => setDraft((d) => ({ ...d, minProbability: Number(e.target.value) }))}>
                {PROBABILITIES.map((p) => (
                  <option key={p} value={p}>
                    {p === 0 ? 'Any' : `≥ ${formatPercent(p)}`}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Minimum reward : risk" hint="Planned gain relative to planned loss.">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={String(draft.minRiskReward)} onChange={(e) => setDraft((d) => ({ ...d, minRiskReward: Number(e.target.value) }))}>
                {RATIOS.map((r) => (
                  <option key={r} value={r}>
                    {r === 0 ? 'Any' : `≥ ${formatRiskReward(r)}`}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Switch
          checked={draft.requireRiskFit}
          onChange={(requireRiskFit) => setDraft((d) => ({ ...d, requireRiskFit }))}
          label="Only show setups that fit my risk limits"
          description="Uses your capital, limits and current exposure from Capital & risk. Without capital, risk checks are shown as “not evaluated”."
        />
      </div>
    </Dialog>
  );
}
