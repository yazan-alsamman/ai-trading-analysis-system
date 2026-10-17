import { zodResolver } from '@hookform/resolvers/zod';
import { ExternalLink, Monitor, Moon, Save, Sun } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge, DemoBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select, Switch } from '@/components/ui/Form';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { TIME_ZONE_OPTIONS } from '@/domain/preferences';
import { useDemoScenario, useNow } from '@/hooks/useEnvironment';
import { useHashScroll } from '@/hooks/useHashScroll';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn } from '@/lib/cn';
import { formatClock, timeZoneLabel } from '@/lib/format';
import { config } from '@/services/config';
import { DEMO_SCENARIOS } from '@/services/demo/scenario';
import { channelSettingsSchema, type ChannelSettingsForm } from './schemas';
import { MembershipSettings } from '@/features/membership/MembershipSettings';
import { WorkspacesSection } from './WorkspacesSection';

function ChannelsSection() {
  const { prefs, setChannels } = usePreferences();
  const { source } = useServices();
  const { notify } = useToast();
  const form = useForm<ChannelSettingsForm>({ resolver: zodResolver(channelSettingsSchema), defaultValues: prefs.channels, mode: 'onTouched' });
  const { register, watch, setValue, formState, handleSubmit, reset } = form;
  const [app, email, telegram] = watch(['app.enabled', 'email.enabled', 'telegram.enabled']);

  const submit = handleSubmit((values) => {
    setChannels(values);
    reset(values);
    notify(source === 'demo' ? 'Channel settings saved in this browser (demo).' : 'Channel settings saved.', 'success');
  });

  return (
    <div id="channels" className="scroll-mt-4">
      <Panel
        title="Notification channels"
        meta={<span>Where alerts and opportunity notifications are delivered</span>}
        actions={
          <Button size="sm" variant="primary" icon={Save} type="submit" form="channels-form" disabled={!formState.isDirty}>
            Save
          </Button>
        }
      >
        <form id="channels-form" noValidate onSubmit={submit} className="flex flex-col divide-y divide-line">
          <div className="pb-4">
            <Switch checked={app} onChange={(v) => setValue('app.enabled', v, { shouldDirty: true })} label="In-app" description="Notifications inside this website." />
          </div>
          <div className="flex flex-col gap-3 py-4">
            <Switch
              checked={email}
              onChange={(v) => setValue('email.enabled', v, { shouldDirty: true, shouldValidate: formState.isSubmitted })}
              label="Email"
              description="Sent to the address below."
            />
            {email && (
              <Field label="Email address" error={formState.errors.email?.address?.message} className="max-w-sm">
                {({ id, describedBy, invalid }) => <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} invalid={invalid} {...register('email.address')} />}
              </Field>
            )}
          </div>
          <div className="flex flex-col gap-3 pt-4">
            <Switch
              checked={telegram}
              onChange={(v) => setValue('telegram.enabled', v, { shouldDirty: true, shouldValidate: formState.isSubmitted })}
              label="Telegram"
              description="Delivered by the project's Telegram bot once the backend links your account."
            />
            {telegram && (
              <Field label="Telegram username" error={formState.errors.telegram?.handle?.message} className="max-w-sm">
                {({ id, describedBy, invalid }) => <Input id={id} placeholder="@username" aria-describedby={describedBy} invalid={invalid} {...register('telegram.handle')} />}
              </Field>
            )}
          </div>
        </form>
        {source === 'demo' && <p className="mt-4 text-xs text-fg-3">Demo: settings are stored in this browser. No notification is sent until the backend service is connected.</p>}
      </Panel>
    </div>
  );
}

function DemoControls() {
  const [scenario, setScenario] = useDemoScenario();
  return (
    <Panel title="Demo controls" meta={<DemoBadge label="Demo only" />}>
      <fieldset>
        <legend className="mb-3 text-sm text-fg-2">Simulate backend conditions to inspect every interface state. Resets when the page reloads.</legend>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {DEMO_SCENARIOS.map((s) => (
            <label
              key={s.id}
              className={cn(
                'flex cursor-pointer gap-2.5 rounded-md border p-3 transition-colors',
                scenario === s.id ? 'border-accent/60 bg-selected' : 'border-line hover:bg-hover',
              )}
            >
              <input type="radio" name="demo-scenario" value={s.id} checked={scenario === s.id} onChange={() => setScenario(s.id)} className="mt-0.5 accent-[var(--accent)]" />
              <span>
                <span className="block text-sm font-medium text-fg">{s.label}</span>
                <span className="block text-xs text-fg-3">{s.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </Panel>
  );
}

export function SettingsPage() {
  const { prefs, setTheme, setDensity, setTimeZone, timeZone } = usePreferences();
  const { source } = useServices();
  const now = useNow(1000);
  useHashScroll();
  usePageTitle('Settings');

  return (
    <Page width="reading">
      <PageHeader title="Settings" description="Display preferences, notification channels and workspaces." />

      <Panel title="Appearance">
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-fg">Theme</p>
              <p className="text-xs text-fg-3">System follows your operating-system setting.</p>
            </div>
            <SegmentedControl
              label="Theme"
              size="md"
              value={prefs.theme}
              onChange={setTheme}
              options={[
                { value: 'system', label: 'System', icon: Monitor },
                { value: 'dark', label: 'Dark', icon: Moon },
                { value: 'light', label: 'Light', icon: Sun },
              ]}
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-fg">Table density</p>
              <p className="text-xs text-fg-3">Compact fits more rows on screen.</p>
            </div>
            <SegmentedControl
              label="Table density"
              size="md"
              value={prefs.density}
              onChange={setDensity}
              options={[
                { value: 'comfortable', label: 'Comfortable' },
                { value: 'compact', label: 'Compact' },
              ]}
            />
          </div>
        </div>
      </Panel>

      <Panel title="Time & display">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Time zone" hint="Market data is stored in UTC; this changes only how times are displayed." className="w-full max-w-sm">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={prefs.timeZone} onChange={(e) => setTimeZone(e.target.value)}>
                {TIME_ZONE_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <p className="num pb-7 text-sm text-fg-2">
            Now: {formatClock(now, timeZone)} {timeZoneLabel(timeZone)}
          </p>
        </div>
      </Panel>

      <ChannelsSection />

      <MembershipSettings />

      <WorkspacesSection
        persistenceNote={
          source === 'demo'
            ? 'Demo: workspaces are saved in this browser only. Server sync per account is pending the backend workspace API.'
            : 'Workspaces are currently saved in this browser. Server sync per account is pending the backend workspace API.'
        }
      />

      <div id="data-source" className="scroll-mt-4">
        <Panel title="Data source" meta={source === 'demo' ? <Badge tone="demo">Demo mode</Badge> : <Badge tone="info">API mode</Badge>}>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[180px_1fr]">
            <dt className="text-fg-3">Mode</dt>
            <dd className="text-fg">
              {source === 'demo'
                ? 'Demo — all prices, AI opportunities, statistics and community content are generated in the browser and labelled “Simulated”.'
                : 'API — data is loaded from the backend.'}
            </dd>
            <dt className="text-fg-3">Backend URL</dt>
            <dd className="num break-all text-fg-2">{source === 'api' ? config.apiBaseUrl : 'Not used in demo mode'}</dd>
            <dt className="text-fg-3">Price updates</dt>
            <dd className="text-fg-2">
              {source === 'demo' ? 'Simulated tick every second while the market is open (Sun 22:00 – Fri 22:00 UTC).' : `Polling every ${config.pricePollMs / 1000}s until a streaming endpoint is available.`}
            </dd>
            <dt className="text-fg-3">Disclaimer</dt>
            <dd className="text-fg-2">
              AI Trading Assistance provides analysis and decision support only. Predictions are probabilistic and can be wrong. Nothing on this site is financial advice,
              and the platform never places, modifies or closes trades.
            </dd>
          </dl>
        </Panel>
      </div>

      {source === 'demo' && <DemoControls />}

      <Panel title="Third-party notices">
        <p className="text-sm text-fg-2">
          Charts are rendered with TradingView Lightweight Charts™ (Apache License 2.0), Copyright © TradingView, Inc.{' '}
          <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline">
            tradingview.com <ExternalLink aria-hidden className="size-3.5" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </p>
      </Panel>
    </Page>
  );
}
