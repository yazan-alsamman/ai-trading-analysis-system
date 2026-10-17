import { Info, Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Checkbox, FormError, Select, Switch } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { CHANNEL_LABELS, type NotificationChannel, type OpportunityAlertPreferences } from '@/domain/alerts';
import { INSTRUMENTS } from '@/domain/instruments';
import { TIMEFRAMES } from '@/domain/market';
import { useResource } from '@/hooks/useResource';
import { formatPercent } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { opportunityPrefsSchema } from './schemas';

const PROBABILITY_STEPS = [0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85];

function toggle<T>(list: T[], item: T, on: boolean): T[] {
  return on ? [...new Set([...list, item])] : list.filter((x) => x !== item);
}

/** SF2 — notifications when a high-probability opportunity is detected. */
export function OpportunityNotifications() {
  const services = useServices();
  const { prefs: userPrefs } = usePreferences();
  const { notify } = useToast();
  const res = useResource('opportunity-prefs', (signal) => services.alerts.getOpportunityPreferences({ signal }));
  const [draft, setDraft] = useState<OpportunityAlertPreferences | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (res.data) setDraft(res.data);
  }, [res.data]);

  const set = (patch: Partial<OpportunityAlertPreferences>) => setDraft((d) => (d ? { ...d, ...patch } : d));
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(res.data);
  const unconfigured = (draft?.channels ?? []).filter((c) => !userPrefs.channels[c].enabled);

  const save = async () => {
    if (!draft) return;
    const parsed = opportunityPrefsSchema.safeParse(draft);
    if (!parsed.success) {
      setErrors(Object.fromEntries(parsed.error.issues.map((i) => [String(i.path[0]), i.message])));
      return;
    }
    setErrors({});
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await services.alerts.saveOpportunityPreferences(parsed.data);
      res.setData(() => saved);
      notify(services.source === 'demo' ? 'Preferences saved in this browser (demo).' : 'Notification preferences saved.', 'success');
    } catch (e) {
      setSaveError(userMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div id="opportunity-notifications" className="scroll-mt-4">
      <Panel
        title="Opportunity notifications"
        meta={<span>Notify me when the AI detects a high-probability opportunity</span>}
        actions={
          draft && (
            <Button variant="primary" size="sm" icon={Save} onClick={save} loading={saving} disabled={!dirty}>
              Save
            </Button>
          )
        }
      >
        {res.status === 'loading' || (!draft && res.status === 'success') ? (
          <Loading label="Loading notification preferences">
            <SkeletonRows rows={4} />
          </Loading>
        ) : !draft ? (
          <ErrorState error={res.error} onRetry={res.reload} compact />
        ) : (
          <div className="flex flex-col gap-5">
            <FormError message={saveError} />
            <Switch
              checked={draft.enabled}
              onChange={(enabled) => set({ enabled })}
              label="Enable opportunity notifications"
              description="Probabilities are model estimates, never guarantees. Notifications report what the model detected; they do not place trades."
            />

            <fieldset disabled={!draft.enabled} className="grid gap-5 disabled:opacity-60 md:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-sm font-medium text-fg">
                Minimum probability
                <Select value={String(draft.minProbability)} onChange={(e) => set({ minProbability: Number(e.target.value) })} className="max-w-48">
                  {PROBABILITY_STEPS.map((p) => (
                    <option key={p} value={p}>
                      ≥ {formatPercent(p)}
                    </option>
                  ))}
                </Select>
              </label>

              <fieldset>
                <legend className="mb-2 text-sm font-medium text-fg">Timeframes & direction</legend>
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                  {TIMEFRAMES.map((t) => (
                    <Checkbox key={t.id} label={t.label} checked={draft.timeframes.includes(t.id)} onChange={(e) => set({ timeframes: toggle(draft.timeframes, t.id, e.target.checked) })} />
                  ))}
                  <span aria-hidden className="w-px bg-line" />
                  {(['long', 'short'] as const).map((d) => (
                    <Checkbox
                      key={d}
                      label={d === 'long' ? 'Long' : 'Short'}
                      checked={draft.directions.includes(d)}
                      onChange={(e) => set({ directions: toggle(draft.directions, d, e.target.checked) })}
                    />
                  ))}
                </div>
                {(errors.timeframes || errors.directions) && <p className="mt-1.5 text-xs text-danger">{errors.timeframes ?? errors.directions}</p>}
              </fieldset>

              <fieldset className="md:col-span-2">
                <legend className="mb-2 text-sm font-medium text-fg">Instruments</legend>
                <div className="grid grid-cols-2 gap-x-5 gap-y-2 sm:grid-cols-4">
                  {INSTRUMENTS.map((i) => (
                    <Checkbox key={i.symbol} label={i.display} checked={draft.symbols.includes(i.symbol)} onChange={(e) => set({ symbols: toggle(draft.symbols, i.symbol, e.target.checked) })} />
                  ))}
                </div>
                {errors.symbols && <p className="mt-1.5 text-xs text-danger">{errors.symbols}</p>}
              </fieldset>

              <fieldset className="md:col-span-2">
                <legend className="mb-2 text-sm font-medium text-fg">Deliver via</legend>
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                  {(['app', 'email', 'telegram'] as NotificationChannel[]).map((c) => (
                    <Checkbox key={c} label={CHANNEL_LABELS[c]} checked={draft.channels.includes(c)} onChange={(e) => set({ channels: toggle(draft.channels, c, e.target.checked) })} />
                  ))}
                </div>
                {errors.channels && <p className="mt-1.5 text-xs text-danger">{errors.channels}</p>}
                {unconfigured.length > 0 && (
                  <p className="mt-2 flex items-start gap-1.5 text-xs text-warning">
                    <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                    {unconfigured.map((c) => CHANNEL_LABELS[c]).join(' and ')} {unconfigured.length > 1 ? 'are' : 'is'} not set up.{' '}
                    <Link to="/settings#channels" className="underline underline-offset-2">
                      Configure channels
                    </Link>
                  </p>
                )}
              </fieldset>
            </fieldset>

            {services.source === 'demo' && (
              <p className="text-xs text-fg-3">Demo: preferences are stored in this browser only. Delivery requires the backend notification service.</p>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
